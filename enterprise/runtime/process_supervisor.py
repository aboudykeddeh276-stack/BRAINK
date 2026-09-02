from __future__ import annotations
from dataclasses import dataclass
import subprocess,os,signal
@dataclass
class ManagedProcess:
    name:str
    argv:list[str]
    proc:subprocess.Popen|None=None
    def start(self):
        if self.proc and self.proc.poll() is None:return self.proc.pid
        self.proc=subprocess.Popen(self.argv,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        return self.proc.pid
    def alive(self)->bool:return bool(self.proc and self.proc.poll() is None)
    def stop(self,timeout:float=3.0):
        if not self.proc or self.proc.poll() is not None:return
        os.killpg(self.proc.pid,signal.SIGTERM)
        try:self.proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(self.proc.pid,signal.SIGKILL);self.proc.wait()
