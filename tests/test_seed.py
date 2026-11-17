import copy,json,tempfile,unittest
from pathlib import Path
from app import Service
from seed_data import load_seed,apply_seed
class SeedTests(unittest.TestCase):
 def test_merge_preserves_results_and_updates_rows(self):
  s=Service(':memory:');data=load_seed();data['mails'][0]['body']='Changed mail';data['events'].append({'id':'e2','owner':'A','title':'New','time':'2026-11-24T15:00:00+09:00'})
  s.db.execute("INSERT INTO grants VALUES ('A','Alpha','member')")
  with s.db:apply_seed(s.db,data)
  with s.db:apply_seed(s.db,data)
  self.assertEqual(s.db.execute("SELECT body FROM mails WHERE id='mail1'").fetchone()[0],'Changed mail')
  self.assertEqual(len(s.state()['events']),2);self.assertEqual(len(s.state()['grants']),1);s.db.close()
 def test_invalid_owner_and_duplicate_are_rejected(self):
  for error in ['owner','duplicate']:
   data=copy.deepcopy(load_seed())
   if error=='owner':data['mails'][0]['owner']='missing'
   else:data['mails'].append(data['mails'][0])
   with tempfile.TemporaryDirectory() as d:
    for k,v in data.items():Path(d,k+'.json').write_text(json.dumps(v))
    with self.assertRaises(ValueError):load_seed(d)
