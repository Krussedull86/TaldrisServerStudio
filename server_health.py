"""Bounded Steam A2S_INFO check, distinct from merely having a live process."""
import socket,struct,time
from pathlib import Path
from config_documents import cfg_fields


def parse_info(data):
    if data[:5]!=b'\xff\xff\xff\xffI' or len(data)<7:raise ValueError('Ukjent query-svar.')
    offset=6;values=[]
    for _ in range(4):
        end=data.find(b'\x00',offset)
        if end<0:raise ValueError('Ufullstendig query-svar.')
        values.append(data[offset:end].decode('utf-8',errors='replace'));offset=end+1
    if len(data)<offset+5:raise ValueError('Ufullstendig spillertall.')
    return dict(name=values[0],map=values[1],players=data[offset+2],max_players=data[offset+3],checked=time.time(),responding=True)


def query(profile,timeout=.6):
    if not profile.get('query_enabled',True):return dict(responding=False,disabled=True,checked=time.time())
    config=(Path(profile['root'])/profile['config']).read_text('utf-8-sig');fields=[field for field in cfg_fields(config) if field['key']=='steamQueryPort']
    if len(fields)!=1:raise ValueError('Steam query-port er ikke entydig.')
    port=int(fields[0]['value']);request=b'\xff\xff\xff\xffTSource Engine Query\x00'
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
        sock.connect(('127.0.0.1',port));sock.settimeout(timeout);sock.send(request);data=sock.recv(65535)
        if data[:5]==b'\xff\xff\xff\xffA' and len(data)==9:sock.send(request+data[5:9]);data=sock.recv(65535)
        return parse_info(data)
