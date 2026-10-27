"""Eight-byte protocol: six 6-bit claims in bytes 0..4, alert in 5..7."""
import cambc as bc

def banking_mode():
    buf=bytearray(5); bc.shared_memory.read(0,buf)
    return bool(buf[4] & 128)

def publish_gems(slot, gems):
    """Late game replaces claims/alerts with six exact 10-bit gem reports.

    Bit 39 is the permanent mode marker; counts skip it. First writer clears
    earlier claims. Reports are refreshed on each owner's turn, including death.
    """
    if not 0 <= slot < 6: return
    buf=bytearray(8);bc.shared_memory.read(0,buf)
    physical=int.from_bytes(buf,'little')
    logical=(physical & ((1<<39)-1)) | ((physical>>40)<<39) if physical & (1<<39) else 0
    shift=slot*10
    logical=(logical & ~(1023<<shift)) | (min(1023,max(0,gems))<<shift)
    physical=(logical & ((1<<39)-1)) | ((logical>>39)<<40) | (1<<39)
    bc.shared_memory.write(0,physical.to_bytes(8,'little'))

def read_gems():
    if not banking_mode(): return [0]*6
    buf=bytearray(8);bc.shared_memory.read(0,buf)
    physical=int.from_bytes(buf,'little')
    logical=(physical & ((1<<39)-1)) | ((physical>>40)<<39)
    return [(logical>>(slot*10)) & 1023 for slot in range(6)]

def read_claims():
    if banking_mode(): return [0]*6
    buf=bytearray(5); bc.shared_memory.read(0,buf)
    value=int.from_bytes(buf,'little')
    return [(value >> (slot*6)) & 63 for slot in range(6)]

def write_claim(slot,index):
    if banking_mode(): return
    if slot>=6: return
    buf=bytearray(5); bc.shared_memory.read(0,buf)
    value=int.from_bytes(buf,'little')
    encoded=index+1 if index is not None and index<63 else 0
    value=(value & ~(63 << (slot*6))) | (encoded << (slot*6))
    bc.shared_memory.write(0,value.to_bytes(5,'little'))

def report(x,y,round_number,danger):
    if banking_mode(): return
    value=x | (y<<7) | ((round_number & 255)<<14) | (1<<22) | (int(danger)<<23)
    bc.shared_memory.write(5,value.to_bytes(3,'little'))

def read_report(round_number):
    if banking_mode(): return 0,None,255
    buf=bytearray(3);bc.shared_memory.read(5,buf)
    value=int.from_bytes(buf,'little')
    return value, ((value & 127,(value>>7)&127) if value & (1<<22) else None), (round_number-((value>>14)&255)) & 255
