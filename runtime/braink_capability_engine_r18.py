from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
import base64, hashlib, hmac, json, os, sqlite3, time, uuid

def _b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()

def _ub64u(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + '=' * (-len(s) % 4))

def canonical_json(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()

def payload_digest(payload: Any) -> str:
    return hashlib.sha256(canonical_json(payload)).hexdigest()

def hkdf_sha256(ikm: bytes, info: bytes, length: int = 32, salt: bytes = b'BRAINK-R18-CAPABILITY') -> bytes:
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    out = b''; t = b''; counter = 1
    while len(out) < length:
        t = hmac.new(prk, t + info + bytes([counter]), hashlib.sha256).digest()
        out += t; counter += 1
    return out[:length]

class CapabilityError(Exception):
    def __init__(self, code: str):
        super().__init__(code); self.code = code

class SQLiteReplayLedger:
    def __init__(self, path: str | os.PathLike[str]):
        self.path = str(path); self._init()
    def _db(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level='IMMEDIATE')
        db.execute('PRAGMA journal_mode=WAL'); db.execute('PRAGMA synchronous=FULL')
        return db
    def _init(self):
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS braink_consumed_nonces(
                nonce TEXT PRIMARY KEY, principal TEXT NOT NULL, exp INTEGER NOT NULL, consumed_at INTEGER NOT NULL)''')
            db.execute('CREATE INDEX IF NOT EXISTS idx_braink_nonce_exp ON braink_consumed_nonces(exp)')
            db.commit()
    def consume(self, nonce: str, principal: str, exp: int, now: Optional[int] = None) -> bool:
        now = int(time.time()) if now is None else int(now)
        with self._db() as db:
            db.execute('DELETE FROM braink_consumed_nonces WHERE exp < ?', (now,))
            try:
                db.execute('INSERT INTO braink_consumed_nonces(nonce, principal, exp, consumed_at) VALUES(?,?,?,?)',
                           (nonce, principal, int(exp), now))
                db.commit(); return True
            except sqlite3.IntegrityError:
                db.rollback(); return False

@dataclass(frozen=True)
class CapabilityClaims:
    version: int; principal: str; product_id: str; operation: str; payload_sha256: str; iat: int; exp: int; nonce: str

class CapabilityEngine:
    def __init__(self, master_secret: bytes, replay_db: str | os.PathLike[str], *, issuer: str = 'BRAINK', max_ttl_seconds: int = 300, clock_skew_seconds: int = 5):
        if len(master_secret) < 32: raise ValueError('master_secret_must_be_at_least_32_bytes')
        self.master_secret = master_secret; self.ledger = SQLiteReplayLedger(replay_db)
        self.issuer = issuer; self.max_ttl = int(max_ttl_seconds); self.skew = int(clock_skew_seconds)
    def _principal_key(self, principal: str) -> bytes:
        return hkdf_sha256(self.master_secret, b'principal:' + principal.encode())
    def issue(self, principal: str, product_id: str, operation: str, payload: Any, *, ttl_seconds: int = 60, now: Optional[int] = None) -> str:
        now = int(time.time()) if now is None else int(now); ttl = int(ttl_seconds)
        if ttl <= 0 or ttl > self.max_ttl: raise CapabilityError('invalid_ttl')
        claims = {'v':1,'iss':self.issuer,'principal':principal,'product_id':product_id,'operation':operation,
                  'payload_sha256':payload_digest(payload),'iat':now,'exp':now+ttl,'nonce':uuid.uuid4().hex}
        body = canonical_json(claims); sig = hmac.new(self._principal_key(principal), body, hashlib.sha256).digest()
        return _b64u(body)+'.'+_b64u(sig)
    def verify(self, token: str, *, principal: str, product_id: str, operation: str, payload: Any, now: Optional[int] = None, consume_nonce: bool = True) -> CapabilityClaims:
        now = int(time.time()) if now is None else int(now)
        try:
            b64body,b64sig = token.split('.',1); body = _ub64u(b64body); sig = _ub64u(b64sig); claims = json.loads(body)
        except Exception: raise CapabilityError('malformed_token')
        required={'v','iss','principal','product_id','operation','payload_sha256','iat','exp','nonce'}
        if set(claims)!=required: raise CapabilityError('claim_shape_invalid')
        if claims['v']!=1 or claims['iss']!=self.issuer: raise CapabilityError('issuer_or_version_invalid')
        claimed_principal=str(claims['principal'])
        expected=hmac.new(self._principal_key(claimed_principal), body, hashlib.sha256).digest()
        if not hmac.compare_digest(expected,sig): raise CapabilityError('bad_signature')
        if claimed_principal!=principal: raise CapabilityError('principal_mismatch')
        if claims['product_id']!=product_id: raise CapabilityError('product_mismatch')
        if claims['operation']!=operation: raise CapabilityError('operation_mismatch')
        if claims['payload_sha256']!=payload_digest(payload): raise CapabilityError('payload_mismatch')
        iat,exp=int(claims['iat']),int(claims['exp'])
        if exp-iat>self.max_ttl or exp<=iat: raise CapabilityError('ttl_invalid')
        if now<iat-self.skew: raise CapabilityError('not_yet_valid')
        if now>exp+self.skew: raise CapabilityError('expired')
        if consume_nonce and not self.ledger.consume(str(claims['nonce']), claimed_principal, exp, now): raise CapabilityError('replay')
        return CapabilityClaims(1,claimed_principal,str(claims['product_id']),str(claims['operation']),str(claims['payload_sha256']),iat,exp,str(claims['nonce']))

def mutating_allowed(engine: CapabilityEngine, token: str, *, principal: str, product_id: str, operation: str, payload: Any, now: Optional[int] = None) -> tuple[bool,str]:
    try:
        engine.verify(token,principal=principal,product_id=product_id,operation=operation,payload=payload,now=now,consume_nonce=True)
        return True,'authorized'
    except CapabilityError as e:
        return False,e.code
