import os, sys, json, struct, subprocess

here = os.path.dirname(os.path.abspath(__file__))
script = os.path.join(here, 'lan_share_host.py')

# Launch the native host as Chrome would (JSON over stdin/stdout)
proc = subprocess.Popen([sys.executable, script], stdin=subprocess.PIPE, stdout=subprocess.PIPE)

req = {"action": "start"}
msg = json.dumps(req).encode('utf-8')
proc.stdin.write(struct.pack('<I', len(msg)))
proc.stdin.write(msg)
proc.stdin.flush()

# Read length-prefixed response
raw_len = proc.stdout.read(4)
if not raw_len:
    print('No response from native host')
    sys.exit(1)

length = struct.unpack('<I', raw_len)[0]
resp = proc.stdout.read(length)
print(resp.decode('utf-8'))
