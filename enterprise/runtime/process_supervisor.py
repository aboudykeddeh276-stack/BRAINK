from dataclasses import dataclass
import subprocess,os,signal,time
@dataclass
class ManagedProcess:
    name:str; argv:list[str]; proc:subprocess.Popen|None=None; generation:int=0; restart_count:int=0; last_failure:str|None=None
    def start(self):
        if self.proc and self.proc.poll() is None:return self.proc.pid
        self.generation+=1
        self.proc=subprocess.Popen(self.argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
        return self.proc.pid
    def alive(self): return bool(self.proc and self.proc.poll() is None)
    def exit_code(self): return None if not self.proc else self.proc.poll()
    def stop(self,timeout=3.0):
        if not self.proc or self.proc.poll() is not None:return
        os.killpg(self.proc.pid,signal.SIGTERM)
        try:self.proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(self.proc.pid,signal.SIGKILL);self.proc.wait()
    def restart(self): self.stop();self.restart_count+=1;return self.start()
    def wait_ready(self,probe,timeout=8.0):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            if not self.alive():
                self.last_failure=f"EXIT_{self.proc.returncode if self.proc else 'UNKNOWN'}";return False
            try:
                if probe(): return True
            except Exception: pass
            time.sleep(.05)
        return False
    def snapshot(self):
        return {"pid":self.proc.pid if self.alive() else None,"alive":self.alive(),"exit_code":self.exit_code(),"generation":self.generation,
                "restart_count":self.restart_count,"last_failure":self.last_failure}
