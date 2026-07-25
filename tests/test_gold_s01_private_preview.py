import copy, importlib.util, json, os, subprocess, tempfile, unittest
from pathlib import Path
from unittest import mock
R=Path(__file__).resolve().parents[1]
def mod(n,p):
 s=importlib.util.spec_from_file_location(n,R/p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
G=mod('gold','scripts/gold_s01_private_preview_v1.py');O=mod('owner','scripts/owner_review_gold_s01_v1.py')
def load(p):return json.loads((R/p).read_text())
def git(r,*a):return subprocess.check_output(['git',*a],cwd=r,text=True,stderr=subprocess.DEVNULL).strip()
def repo(fs):
 r=Path(tempfile.mkdtemp());git(r,'init','-q');git(r,'config','user.email','t@invalid');git(r,'config','user.name','T')
 for n,b in fs.items():p=r/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
 git(r,'add','.');git(r,'commit','-qm','f');return r,git(r,'rev-parse','HEAD')
class T(unittest.TestCase):
 def setUp(s):s.p=load('config/gold_s01_private_preview_profile_v1.json');s.r=load('fixtures/gold_s01_private_preview/positive_request.json')
 def err(s,c,f,*a,**k):
  with s.assertRaises(G.PreviewError) as x:f(*a,**k)
  s.assertEqual(x.exception.code,c)
 def probe(s,k):
  e=s.p['expected_outputs'][k];v={'codec_type':'video','codec_name':e['video_codec'],'pix_fmt':e['pixel_format'],'width':e['width'],'height':e['height'],'avg_frame_rate':'30/1'};z=[v]
  if k=='ru_preview':z+=[{'codec_type':'audio','codec_name':'aac','channels':2,'sample_rate':'48000'}]
  return {'format':{'format_name':e['container']},'streams':z}
 def test_contracts_and_mutations(s):
  G.validate_profile(s.p);s.assertEqual(G.validate_request(s.r,s.p)['validation_status'],'ACCEPTED_INPUTS_READY')
  q=load('fixtures/gold_s01_private_preview/provisional_request.json');s.assertIn('ACCEPTED_TIMING_MISSING',G.validate_request(q,s.p,allow_provisional=True)['blockers']);s.err('FINAL_RENDER_INPUTS_NOT_ACCEPTED',G.validate_request,q,s.p)
  ms=[('FINAL_RENDER_INPUTS_NOT_ACCEPTED',lambda r:r['timing'].update(unresolved_rows=1)),('IDENTITY_INVALID',lambda r:r['timing'].update(accepted_contract_sha256='bad')),('FINAL_RENDER_INPUTS_NOT_ACCEPTED',lambda r:r['captions'].update(final=False)),('IDENTITY_INVALID',lambda r:r['captions'].update(sha256='bad')),('VISUAL_SCENE_COUNT_MISMATCH',lambda r:r['visual'].update(scene_ir_count=25)),('ASSET_FINGERPRINT_MISMATCH',lambda r:r['visual']['no_render_manifest'].update(visual_input_fingerprint='f'*64)),('FINAL_RENDER_INPUTS_NOT_ACCEPTED',lambda r:r.update(execution_authorized=False)),('REQUEST_POLICY_INVALID',lambda r:r.update(arbitrary_commands_allowed=True)),('UNSAFE_RELATIVE_PATH',lambda r:r['captions'].update(path='../../x'))]
  for c,m in ms:q=copy.deepcopy(s.r);m(q);s.err(c,G.validate_request,q,s.p)
  for k in ('command','script_path','provider_payload'):q=copy.deepcopy(s.r);q[k]='x';s.err('DYNAMIC_EXECUTION_FIELD_FORBIDDEN',G.validate_request,q,s.p)
 def test_public_execution_and_exact_head(s):
  with mock.patch.dict(os.environ,{'GITHUB_ACTIONS':'true'},clear=False):s.err('PUBLIC_WORKFLOW_PRIVATE_EXECUTION_FORBIDDEN',G.require_private_execution_host)
  r,h=repo({'a':b'a'});G.validate_git_checkout(r,h);s.err('EXACT_HEAD_DRIFT',G.validate_git_checkout,r,'0'*40);(r/'a').write_bytes(b'b');s.err('CHECKOUT_DIRTY',G.validate_git_checkout,r,h)
 def test_materialization_exact_hashes(s):
  p=copy.deepcopy(s.p);q=copy.deepcopy(s.r);a=p['fixed_production_adapter_path'];m=q['visual']['no_render_manifest']['path'];t=q['timing']['accepted_contract_path'];c=q['captions']['path'];l=p['runtime_lock']['package_lock_path'];rp=q['control']['request_path'];r,h=repo({a:b'a',m:b'm',t:b't',c:b'c',l:b'lock',rp:b'{}'})
  q['runner']['sha']=q['control']['sha']=q['production']['sha']=h;q['visual']['visual_runtime_head']=h;q['visual']['production_adapter_git_blob_sha']=git(r,'hash-object',a);q['visual']['no_render_manifest'].update(git_blob_sha=git(r,'hash-object',m),sha256=G.sha256_file(r/m));q['timing']['accepted_contract_sha256']=G.sha256_file(r/t);q['captions']['sha256']=G.sha256_file(r/c);p['runtime_lock'].update(package_lock_git_blob_sha=git(r,'hash-object',l),package_lock_sha256=G.sha256_file(r/l),package_lock_size_bytes=4);f=G.compute_visual_input_fingerprint(q);q['visual']['visual_input_fingerprint']=f;q['visual']['no_render_manifest']['visual_input_fingerprint']=f
  with mock.patch.dict(os.environ,{'GITHUB_ACTIONS':'false'},clear=False):
   s.assertEqual(G.materialize_and_verify_inputs(q,p,r,r,r)['visual_input_fingerprint'],f);(r/c).write_text('bad');s.err('CHECKOUT_DIRTY',G.materialize_and_verify_inputs,q,p,r,r,r)
 def test_store_replica_restore_overwrite_and_codec(s):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);o={'clean_visual_master':d/'c','ru_preview':d/'p'};o['clean_visual_master'].write_bytes(b'c');o['ru_preview'].write_bytes(b'p');q=G.validate_request(s.r,s.p);z={k:s.probe(k) for k in o};a,b,c=G.register_outputs(o,z,s.p,d/'private',q);s.assertEqual((a['registration_status'],b['replica_status'],c['restore_status'],c['cleanup_status']),('PASS','PASS','PASS','PASS'));i=a['artifacts'][0];x=d/'private/gold_s01_primary_v1/sha256'/i['sha256'][:2]/i['sha256']/s.p['expected_outputs'][i['artifact_type']]['filename'];x.write_bytes(b'bad');s.err('CONTENT_ADDRESS_OVERWRITE_REJECTED',G.register_outputs,o,z,s.p,d/'private',q)
  for k in ('clean_visual_master','ru_preview'):G.validate_ffprobe(s.probe(k),s.p['expected_outputs'][k],k)
  z=s.probe('ru_preview');z['streams'][1]['channels']=1;s.err('FFPROBE_AUDIO_PROFILE_MISMATCH',G.validate_ffprobe,z,s.p['expected_outputs']['ru_preview'],'ru_preview')
 def test_corrupted_copy(s):
  with tempfile.TemporaryDirectory() as d:
   a,b=Path(d)/'a',Path(d)/'b';a.write_bytes(b'a');b.write_bytes(b'b');s.err('CONTENT_ADDRESS_OVERWRITE_REJECTED',G.copy_verified,a,b,G.sha256_file(a),1)
 def test_idempotent_failure_resume(s):
  q=G.validate_request(s.r,s.p);calls={}
  def run(n):calls[n]=calls.get(n,0)+1;return {'status':'GREEN'}
  with tempfile.TemporaryDirectory() as d:
   f=Path(d)/'s.json'
   with s.assertRaises(G.RetryablePreviewError) as x:G.run_state_machine(q,s.p,f,run,inject_failure_after_station='03_NO_RENDER_VALIDATE')
   s.assertTrue(G.run_state_machine(q,s.p,f,run,resume_token=x.exception.token)['completed']);G.run_state_machine(q,s.p,f,run);s.assertEqual(calls['03_NO_RENDER_VALIDATE'],1);s.assertEqual(sum(calls.values()),15)
 def test_host_probe_owner_and_public_diagnostic(s):
  with tempfile.TemporaryDirectory() as d:
   x=G.host_probe(s.p,Path(d),authorize_store_probe=True);s.assertEqual((x['primary_probe'],x['replica_probe']),('PASS','PASS'));s.assertIn('NODE_VERSION_LOCK_UNPUBLISHED',x['blockers']);r=O.write_decision(Path(d)/'d.json','r','a'*64,'REPAIR_REQUIRED');s.assertFalse(r['human_final_preview_accepted']);s.assertTrue(r['local_only'])
   with s.assertRaises(O.OwnerReviewError):O.write_decision(Path(d)/'d.json','r','a'*64,'MAYBE')
  x=G.public_diagnostic(s.p);s.assertFalse(x['private_media_execution']);s.assertEqual(x['actions_steps_none_classification'],'PRE_STEP_INFRASTRUCTURE_FAILURE_NOT_CODE_VERDICT')
if __name__=='__main__':unittest.main()
