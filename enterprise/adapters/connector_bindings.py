from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple
@dataclass(frozen=True)
class ConnectorBinding:
    capability:str
    provider:str
    state:str
    operations:Tuple[str,...]
    proof_reference:str
MAIL=ConnectorBinding("mail","Gmail","BOUND_CONTROL_PLANE",("search","read","label","draft","send"),"Gmail runtime label mutation observed")
IDENTITY=ConnectorBinding("identity","Google Contacts","BOUND_READ_ONLY",("search","read"),"Contacts identity lookup observed")
CALENDAR=ConnectorBinding("calendar","Google Calendar","BOUND_READ_ONLY",("search","read","create","update","delete"),"Calendar metadata readback observed; write not side-effect tested")
DRIVE=ConnectorBinding("drive","Google Drive","BOUND_AND_TESTED",("search","read","create_folder","create_file","upload","update"),"KEDDEH_SYSTEMS_RUNTIME_BINDINGS folder creation observed")
