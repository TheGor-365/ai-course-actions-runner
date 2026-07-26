import copy, importlib.util, json, os, subprocess, tempfile, unittest
from pathlib import Path
from unittest import mock
R=Path(__file__).resolve().parents[1]
def mod(n,p):
 s=importlib.util.spec_from_file_location(n,R/p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
G=mod('gold','scripts/gold_s01_private_preview_v1.py')
def load(p):return json.loads((R/p).read_text())
def git(r,*a):return subprocess.check_output(['git',*a],cwd=r,text=True,stderr=subprocess.DEVNULL).strip()
def repo(fs, parent=None):
 r=Path(tempfile.mkdtemp()) if parent is None else parent
 if parent is None:git(r,'init','-q');git(r,'config','user.email','t@invalid');git(r,'config','user.name','T')
 for n,b in fs.items():p=r/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
 git(r,'add','.');git(r,'commit','-qm','f');return r,git(r,'rev-parse','HEAD')
def embed(v):v['receipt_hash']=G.canonical_hash(v);return v
class T(unittest.TestCase):
 def setUp(s):s.p=load('config/gold_s01_private_preview_profile_v1.json');s.r=load('fixtures/gold_s01_private_preview/positive_request.json')
 def err(s,c,f,*a,**k):
  with s.assertRaises(G.PreviewError) as x:f(*a,**k)
  s.assertEqual(x.exception.code,c)
 def probe(s,k):
  e=s.p['expected_outputs'][k];v={'codec_type':'video','codec_name':e['video_codec'],'pix_fmt':e['pixel_format'],'width':e['width'],'height':e['height'],'avg_frame_rate':'30/1'};z=[v]
  if k=='ru_preview':z+=[{'codec_type':'audio','codec_name':'aac','channels':2,'sample_rate':'48000'}]
  return {'format':{'format_name':e['container']},'streams':z}
 def host_receipt(s):
  tools={k:{'command':k,'version':('ffmpeg version 6.1.1-3ubuntu5' if k=='ffmpeg' else 'ffprobe version 6.1.1-3ubuntu5' if k=='ffprobe' else 'v1'),'executable_sha256':('1' if k!='npm' else '2')*64,'size_bytes':1,'filename':k} for k in s.p['host_lock_policy']['required_commands']}
  fonts=[{'alias':a,'family':a,'style':'Regular','filename':a+'.ttf','sha256':('3' if a=='sans-serif' else '4')*64,'size_bytes':1} for a in s.p['host_lock_policy']['required_font_aliases']]
  v={'schema_version':G.HOST_RECEIPT_SCHEMA,'profile_id':s.p['profile_id'],'platform':'linux','machine':'x86_64','github_actions':False,'private_execution_allowed':True,'tools':tools,'browser':{'command':'chromium','selected_candidate':'chromium','version':'Chromium 1','executable_sha256':'5'*64,'size_bytes':1,'filename':'chromium'},'fonts':fonts,'package_lock':{'git_blob_sha':s.p['runtime_lock']['package_lock_git_blob_sha'],'sha256':s.p['runtime_lock']['package_lock_sha256'],'size_bytes':s.p['runtime_lock']['package_lock_size_bytes'],'lockfile_version':3,'resolved_versions':s.p['runtime_lock']['resolved_versions']},'private_root':{'exists':True,'writable':True,'mode':448,'free_bytes':s.p['minimum_free_bytes']+1},'minimum_free_bytes':s.p['minimum_free_bytes'],'blockers':[],'install_plan':[],'media_created':False,'public_artifacts_created':False,'private_content_public_exposure':False,'raw_private_paths_in_receipt':False,'no_fake_green':True,'observed_at':'2026-01-01T00:00:00Z'}
  v['font_manifest_sha256']=G.hashlib.sha256(G.canonical_bytes(fonts)).hexdigest();v['lock_fingerprint']='6'*64;v['host_lock_status']='READY';return embed(v)
 def audio_handoff(s):
  return embed({'schema_version':G.AUDIO_HANDOFF_SCHEMA,'audio_head':'3'*40,'accepted_timing_path':'sanitized_timing_handoff_v01/timing.json','accepted_timing_sha256':'9'*64,'final_ru_captions_path':'sanitized_timing_handoff_v01/captions.json','final_ru_captions_sha256':'a'*64,'unresolved_rows':0,'timing_authority_accepted':True,'a3483_sha256':G.A3483_SHA256,'no_fake_green':True})
 def visual_handoff(s,result='PASS',authorized=True):
  return embed({'schema_version':G.VISUAL_HANDOFF_SCHEMA,'runner_pr':15,'runner_head':'8'*40,'private_pr':349,'private_branch':'repair/gold-s01-visual-runtime-v2','private_sha':'4'*40,'result':result,'production_adapter_path':s.p['fixed_production_adapter_path'],'production_adapter_git_blob_sha':'5'*40,'full_composition_id':'GoldS01FullVisualMaster','full_composition_registered':True,'execution_authorized':authorized,'final_render_authorized':authorized,'private_render_request_status':'EXECUTION_AUTHORIZED_EXACT_INPUTS' if authorized else 'READY_NON_PROVISIONAL_VISUAL_INPUTS','no_render_manifest_path':'03_modules/M1/L01/gold_v2/no_render_manifest.json','no_render_manifest_git_blob_sha':'6'*40,'no_render_manifest_sha256':'7'*64,'visual_input_fingerprint':'f'*64,'private_render_request_sha256':'e'*64,'shot_ir_count':26,'scene_ir_count':26,'no_fake_green':True})
 def test_contracts_and_mutations(s):
  G.validate_profile(s.p);s.assertEqual(G.validate_request(s.r,s.p)['validation_status'],'ACCEPTED_INPUTS_READY')
  q=load('fixtures/gold_s01_private_preview/provisional_request.json');b=G.validate_request(q,s.p,allow_provisional=True)['blockers'];s.assertIn('VISUAL_EXACT_GATE_NOT_PASS',b);s.assertIn('HOST_LOCK_RECEIPT_MISSING',b);s.err('FINAL_RENDER_INPUTS_NOT_ACCEPTED',G.validate_request,q,s.p)
  ms=[('FINAL_RENDER_INPUTS_NOT_ACCEPTED',lambda r:r['timing'].update(unresolved_rows=1)),('IDENTITY_INVALID',lambda r:r['timing'].update(accepted_contract_sha256='bad')),('FINAL_RENDER_INPUTS_NOT_ACCEPTED',lambda r:r['captions'].update(final=False)),('VISUAL_SCENE_COUNT_MISMATCH',lambda r:r['visual'].update(scene_ir_count=25)),('ASSET_FINGERPRINT_MISMATCH',lambda r:r['visual']['no_render_manifest'].update(visual_input_fingerprint='0'*64)),('FINAL_RENDER_INPUTS_NOT_ACCEPTED',lambda r:r.update(execution_authorized=False)),('REQUEST_POLICY_INVALID',lambda r:r.update(arbitrary_commands_allowed=True)),('UNSAFE_RELATIVE_PATH',lambda r:r['captions'].update(path='../../x')),('VISUAL_GATE_HEAD_MISMATCH',lambda r:r['visual_gate'].update(private_sha='0'*40)),('FINAL_RENDER_INPUTS_NOT_ACCEPTED',lambda r:r['host_authority'].update(status='BLOCKED')),('FINAL_RENDER_INPUTS_NOT_ACCEPTED',lambda r:r['store_probe_authority'].update(status='FAIL'))]
  for c,m in ms:q=copy.deepcopy(s.r);m(q);s.err(c,G.validate_request,q,s.p)
  for k in ('command','script_path','provider_payload'):q=copy.deepcopy(s.r);q[k]='x';s.err('DYNAMIC_EXECUTION_FIELD_FORBIDDEN',G.validate_request,q,s.p)
 def test_public_execution_and_exact_head(s):
  with mock.patch.dict(os.environ,{'GITHUB_ACTIONS':'true'},clear=False):s.err('PUBLIC_WORKFLOW_PRIVATE_EXECUTION_FORBIDDEN',G.require_private_execution_host)
  r,h=repo({'a':b'a'});G.validate_git_checkout(r,h);s.err('EXACT_HEAD_DRIFT',G.validate_git_checkout,r,'0'*40);(r/'a').write_bytes(b'b');s.err('CHECKOUT_DIRTY',G.validate_git_checkout,r,h)
 def test_materialization_exact_hashes(s):
  p=copy.deepcopy(s.p);q=copy.deepcopy(s.r);a=p['fixed_production_adapter_path'];m=q['visual']['no_render_manifest']['path'];l=p['runtime_lock']['package_lock_path'];pr,ph=repo({a:b'a',m:b'm',l:b'lock'});rr,rh=repo({'r':b'r'})
  p['runtime_lock'].update(package_lock_git_blob_sha=git(pr,'hash-object',l),package_lock_sha256=G.sha256_file(pr/l),package_lock_size_bytes=4);q['runner']['sha']=rh;q['production']['sha']=ph;q['visual']['visual_runtime_head']=ph;q['visual_gate']['private_sha']=ph;q['visual']['production_adapter_git_blob_sha']=git(pr,'hash-object',a);q['visual']['no_render_manifest'].update(git_blob_sha=git(pr,'hash-object',m),sha256=G.sha256_file(pr/m));q['visual_gate']['no_render_manifest_sha256']=G.sha256_file(pr/m)
  audio=Path(tempfile.mkdtemp());t=audio/q['timing']['accepted_contract_path'];c=audio/q['captions']['path'];t.parent.mkdir(parents=True,exist_ok=True);t.write_bytes(b't');c.write_bytes(b'c');q['timing']['accepted_contract_sha256']=G.sha256_file(t);q['captions']['sha256']=G.sha256_file(c)
  cr=Path(tempfile.mkdtemp());git(cr,'init','-q');git(cr,'config','user.email','t@invalid');git(cr,'config','user.name','T');(cr/'base').write_bytes(b'b');git(cr,'add','.');git(cr,'commit','-qm','base');base=git(cr,'rev-parse','HEAD');q['control']['sha']=base;rp=cr/q['control']['request_path'];rp.parent.mkdir(parents=True,exist_ok=True);rp.write_text(json.dumps(q,sort_keys=True));git(cr,'add','.');git(cr,'commit','-qm','request');ch=git(cr,'rev-parse','HEAD');blob=git(cr,'hash-object',str(rp.relative_to(cr)))
  with mock.patch.dict(os.environ,{'GITHUB_ACTIONS':'false'},clear=False):
   x=G.materialize_and_verify_inputs(q,p,rr,cr,pr,audio,control_head_sha=ch,request_blob_sha=blob);s.assertEqual(x['request_blob_sha'],blob);c.write_text('bad');s.err('AUDIO_AUTHORITY_HASH_MISMATCH',G.materialize_and_verify_inputs,q,p,rr,cr,pr,audio,control_head_sha=ch,request_blob_sha=blob)
 def test_store_replica_restore_overwrite_and_codec(s):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);o={'clean_visual_master':d/'c','ru_preview':d/'p'};o['clean_visual_master'].write_bytes(b'c');o['ru_preview'].write_bytes(b'p');q=G.validate_request(s.r,s.p);z={k:s.probe(k) for k in o};a,b,c=G.register_outputs(o,z,s.p,d/'private',q);s.assertEqual((a['registration_status'],b['replica_status'],c['restore_status'],c['cleanup_status']),('PASS','PASS','PASS','PASS'));i=a['artifacts'][0];x=d/'private/gold_s01_primary_v1/sha256'/i['sha256'][:2]/i['sha256']/s.p['expected_outputs'][i['artifact_type']]['filename'];x.write_bytes(b'bad');s.err('CONTENT_ADDRESS_OVERWRITE_REJECTED',G.register_outputs,o,z,s.p,d/'private',q)
  for k in ('clean_visual_master','ru_preview'):G.validate_ffprobe(s.probe(k),s.p['expected_outputs'][k],k)
  z=s.probe('ru_preview');z['streams'][1]['channels']=1;s.err('FFPROBE_AUDIO_PROFILE_MISMATCH',G.validate_ffprobe,z,s.p['expected_outputs']['ru_preview'],'ru_preview')
 def test_host_and_store_receipts(s):
  h=s.host_receipt();G.validate_host_locks(h,s.p,h['receipt_hash']);q=copy.deepcopy(h);q['lock_fingerprint']='0'*64;s.err('RECEIPT_HASH_MISMATCH',G.validate_host_locks,q,s.p)
  with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ,{'GITHUB_ACTIONS':'false'},clear=False):
   d=Path(d);r=G.store_probe(s.p,d/'p',d/'r');G.validate_store_probe_receipt(r,s.p,r['receipt_hash']);s.assertEqual(r['probe_status'],'PASS');s.assertFalse(any((d/'p').glob('.gold-s01-probe-*')))
  with mock.patch.dict(os.environ,{'GITHUB_ACTIONS':'true'},clear=False):s.err('PUBLIC_WORKFLOW_PRIVATE_EXECUTION_FORBIDDEN',G.store_probe,s.p,Path('/tmp/a'),Path('/tmp/b'))
 def test_rebind_idempotent_and_stale_rejection(s):
  p=load('fixtures/gold_s01_private_preview/provisional_request.json');h=s.host_receipt()
  with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ,{'GITHUB_ACTIONS':'false'},clear=False):store=G.store_probe(s.p,Path(d)/'p',Path(d)/'r')
  s.err('VISUAL_EXACT_GATE_NOT_PASS',G.rebind_request,p,s.audio_handoff(),s.visual_handoff('FAIL'),h,store,s.p,runner_sha='1'*40,control_base_sha='2'*40,authorize=True)
  s.err('VISUAL_RENDER_AUTHORITY_ABSENT',G.rebind_request,p,s.audio_handoff(),s.visual_handoff(authorized=False),h,store,s.p,runner_sha='1'*40,control_base_sha='2'*40,authorize=True)
  bad=s.visual_handoff();bad['production_adapter_path']='wrong.py';bad=embed({k:v for k,v in bad.items() if k!='receipt_hash'});s.err('PRODUCTION_ADAPTER_PATH_MISMATCH',G.rebind_request,p,s.audio_handoff(),bad,h,store,s.p,runner_sha='1'*40,control_base_sha='2'*40,authorize=True)
  req,rec=G.rebind_request(p,s.audio_handoff(),s.visual_handoff(),h,store,s.p,runner_sha='1'*40,control_base_sha='2'*40,authorize=True);s.assertTrue(req['execution_authorized']);s.assertEqual(rec['status'],'EXACT_AUTHORIZED')
  with tempfile.TemporaryDirectory() as d:
   out=Path(d)/'request.json';rp=Path(d)/'receipt.json';s.assertEqual(G.atomic_rebind(out,req,rec,rp),'REPLACED_PROVISIONAL');s.assertEqual(G.atomic_rebind(out,req,rec,rp),'UNCHANGED');q=copy.deepcopy(req);q['request_id']='other';s.err('EXACT_REQUEST_REBIND_CONFLICT',G.atomic_rebind,out,q,rec,rp)
 def test_idempotent_failure_resume(s):
  q=G.validate_request(s.r,s.p);calls={}
  def run(n):calls[n]=calls.get(n,0)+1;return {'status':'GREEN'}
  with tempfile.TemporaryDirectory() as d:
   f=Path(d)/'s.json'
   with s.assertRaises(G.RetryablePreviewError) as x:G.run_state_machine(q,s.p,f,run,inject_failure_after_station='03_NO_RENDER_VALIDATE')
   s.assertTrue(G.run_state_machine(q,s.p,f,run,resume_token=x.exception.token)['completed']);G.run_state_machine(q,s.p,f,run);s.assertEqual(calls['03_NO_RENDER_VALIDATE'],1);s.assertEqual(sum(calls.values()),15)
if __name__=='__main__':unittest.main()
