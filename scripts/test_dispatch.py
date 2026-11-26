import importlib.util,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
SCRIPT=Path(__file__).with_name('dispatch.py')
spec=importlib.util.spec_from_file_location('dispatch',SCRIPT);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Tests(unittest.TestCase):
 def setUp(self):
  self.root=Path(tempfile.mkdtemp(prefix='claude-skill-test-'))
  self.packet=self.root/'packet';self.packet.mkdir();(self.packet/'TASK.md').write_text('Offline test')
  (self.packet/'source.py').write_text('value=1\n')
 def fake(self,body):
  p=self.root/'fake_claude';p.write_text('#!'+sys.executable+'\n'+body);p.chmod(0o700);return p
 def runfake(self,body,timeout=5):
  fake=self.fake(body)
  p=subprocess.run([sys.executable,str(SCRIPT),'run','--packet',str(self.packet),'--claude-bin',str(fake),'--timeout',str(timeout)],text=True,capture_output=True,timeout=15)
  lines=p.stdout.splitlines();batch=Path(json.loads(lines[0])['batch']);r=json.loads((batch/'packet.receipt.json').read_text());return p,r,batch
 def test_success_does_not_edit_original(self):
  p,r,b=self.runfake("import pathlib,json,sys\nsys.stdin.read()\npathlib.Path('source.py').write_text('value=2\\n')\npathlib.Path('RESULT.md').write_text('done')\nprint(json.dumps({'type':'result','is_error':False,'modelUsage':{'claude-opus-5-5':{}},'permission_denials':[],'usage':{'input_tokens':2}}))\n")
  self.assertEqual(p.returncode,0);self.assertEqual(r['state'],'completed');self.assertEqual(set(r['changed']),{'source.py','RESULT.md'});self.assertEqual((self.packet/'source.py').read_text(),'value=1\n')
  status=subprocess.run([sys.executable,str(SCRIPT),'status','--batch',str(b)],capture_output=True,text=True,check=True)
  self.assertNotIn('before',json.loads(status.stdout));self.assertNotIn('usage',json.loads(status.stdout))
 def test_model_effort_and_provider_routing_receipt(self):
  p,r,_=self.runfake("import json,sys\na=sys.argv\nassert a[a.index('--model')+1]=='claude-opus-5-5'\nassert a[a.index('--effort')+1]=='medium'\nsys.stdin.read()\nprint(json.dumps({'type':'result','is_error':False,'modelUsage':{'claude-opus-5-5':{},'claude-opus-4-8':{}},'safety_stops':2}))\n")
  self.assertEqual(p.returncode,1)
  self.assertEqual(r['state'],'model_mismatch')
  self.assertFalse(r['output_accepted'])
  self.assertEqual(r['model_detection']['event_type'],'result')
  self.assertEqual(r['requested_model'],'claude-opus-5-5')
  self.assertEqual(r['requested_effort'],'medium')
  self.assertEqual(r['actual_models'],['claude-opus-4-8','claude-opus-5-5'])
  self.assertEqual(r['safety_stops'],2)
  self.assertEqual(r['packet_files'],2)
  self.assertEqual(r['packet_bytes'],sum(x.stat().st_size for x in self.packet.iterdir()))
  self.assertEqual(len(r['largest_inputs']),2)
 def test_stream_mismatch_stops_before_later_side_effect(self):
  body="""import json,sys,time,pathlib
sys.stdin.read()
assert sys.argv[sys.argv.index('--output-format')+1]=='stream-json'
assert '--no-session-persistence' in sys.argv
assert '--include-partial-messages' in sys.argv
print(json.dumps({'type':'stream_event','event':{'type':'message_start','message':{'model':'claude-opus-4-8'}}}),flush=True)
time.sleep(3)
pathlib.Path('should-not-exist').write_text('late side effect')
"""
  p,r,b=self.runfake(body)
  self.assertEqual(p.returncode,1);self.assertEqual(r['state'],'model_mismatch')
  self.assertFalse((b/'packet'/'should-not-exist').exists())
  self.assertFalse(r['output_accepted']);self.assertEqual(r['actual_models'],['claude-opus-4-8'])
  with self.assertRaises(ProcessLookupError):os.kill(r['pid'],0)
 def test_missing_actual_model_is_not_accepted(self):
  p,r,_=self.runfake("import json,sys\nsys.stdin.read()\nprint(json.dumps({'type':'system','subtype':'init','model':'claude-opus-5-5'}))\nprint(json.dumps({'type':'result','is_error':False}))\n")
  self.assertEqual(p.returncode,1);self.assertEqual(r['state'],'model_unverified');self.assertFalse(r['output_accepted'])
 def test_assistant_model_counts_but_text_does_not(self):
  p,r,_=self.runfake("import json,sys\nsys.stdin.read()\nprint(json.dumps({'type':'assistant','message':{'model':'claude-opus-5-5','content':[{'type':'text','text':'claude-opus-4-8'}]}}))\nprint(json.dumps({'type':'result','is_error':False}))\n")
  self.assertEqual(p.returncode,0);self.assertTrue(r['output_accepted']);self.assertEqual(r['actual_models'],['claude-opus-5-5'])
 def test_partial_lines_and_invalid_json(self):
  p,r,_=self.runfake("import json,sys,time\nsys.stdin.read()\nprint('diagnostic',flush=True)\ne=json.dumps({'type':'result','is_error':False,'modelUsage':{'claude-opus-5-5':{}}})\nsys.stdout.write(e[:30]);sys.stdout.flush();time.sleep(.05);sys.stdout.write(e[30:]);sys.stdout.flush()\n")
  self.assertEqual(p.returncode,0);self.assertEqual(r['state'],'completed')
 def test_error_is_not_accepted(self):
  p,r,_=self.runfake("import json,sys\nsys.stdin.read()\nprint(json.dumps({'type':'result','is_error':True,'modelUsage':{'claude-opus-5-5':{}}}))\n")
  self.assertEqual(p.returncode,1);self.assertFalse(r['output_accepted']);self.assertEqual(r['state'],'failed')
 def test_timeout_is_terminal(self):
  p,r,_=self.runfake('import sys,time\nsys.stdin.read()\ntime.sleep(20)\n',timeout=.1)
  self.assertEqual(p.returncode,1);self.assertEqual(r['state'],'timed_out')
  with self.assertRaises(ProcessLookupError):os.kill(r['pid'],0)
 def test_symlink_rejected(self):
  (self.packet/'outside').symlink_to('/etc/hosts')
  with self.assertRaises(ValueError):m.copy_packet(self.packet,self.root/'copy')
if __name__=='__main__':unittest.main()
