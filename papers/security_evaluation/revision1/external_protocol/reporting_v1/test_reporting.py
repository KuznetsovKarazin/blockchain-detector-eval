"""Synthetic numerical and identity checks; never actual references/scores."""
from itertools import combinations
from pathlib import Path
import sys,unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).parent))
import reporting as r
from synthetic_inputs import fixture,evaluate

class ReportingTests(unittest.TestCase):
    def setUp(self):self.data,self.key=fixture()
    def report(self,**kwargs):return evaluate(self.data,self.key,**kwargs)
    def job(self,method='raw_tfidf_lr',seed=0):return f'{method}:reentrancy:{seed}'
    def fail(self,path,job=None):
        mask=self.data[-1].path.eq(path)&self.data[-1].job_id.eq(job or self.job())
        self.data[-1].loc[mask,['status','execution_status']]='timeout';self.data[-1].loc[mask,'score']=np.nan
    def test_exact13vectors12rawreference_contrasts_and_no_default_bootstrap(self):
        with patch.object(r.v2,'evaluate_methods',side_effect=AssertionError('No default bootstrap')):
            out=self.report()
        self.assertEqual(len(out['primary_inventory']),13);self.assertIsNone(out['exploratory']);self.assertIsNone(out['engine_audit'])
        for d in out['primary']['domains'].values():
            self.assertEqual(len(d['vectors']),13);self.assertEqual(len(d['raw_LR_reference_contrasts']),12)
            self.assertTrue(all(x['right']==self.job() for x in d['raw_LR_reference_contrasts']))
            self.assertIsNone(d['reference_positive_total']['confidence_interval'])
    def test_missing_vector_rejected(self):
        self.data[-1]=self.data[-1][~self.data[-1].job_id.eq(self.job('pattern_rf',4))]
        with self.assertRaises(ValueError):self.report()
    def test_reused_job_id_seed_rejected(self):
        self.data[-1].loc[self.data[-1].job_id.eq(self.job('pattern_rf',1)),'job_id']=self.job('pattern_rf',0)
        with self.assertRaises(ValueError):self.report()
    def test_seed_metadata_rejected(self):
        self.data[-1].loc[self.data[-1].job_id.eq(self.job()),'seed']=1
        with self.assertRaises(ValueError):self.report()
    def test_duplicate_score_unit_rejected(self):
        self.data[-1]=pd.concat([self.data[-1],self.data[-1].iloc[[0]]])
        with self.assertRaises(ValueError):self.report()
    def test_case_to_other_valid_file_rejected_by_separate_manifest(self):
        self.data[1].loc[0,'path']='synthetic://file_0001'
        with self.assertRaisesRegex(ValueError,'frozen case manifest'):self.report()
    def test_review_case_class_mismatch_rejected(self):
        self.data[5].loc[0,'class']='unchecked'
        with self.assertRaisesRegex(ValueError,'case/class'):self.report()
    def test_optional_review_path_mismatch_rejected(self):
        self.data[5]['path']=self.data[5].case_id.map(self.key.set_index('case_id').path)
        self.data[5].loc[0,'path']='synthetic://file_0001'
        with self.assertRaisesRegex(ValueError,'case/file'):self.report()
    def test_duplicate_case_rejected(self):
        self.data[5].loc[1,'case_id']=self.data[5].loc[0,'case_id']
        with self.assertRaises(ValueError):self.report()
    def test_failed_score_cannot_receive_safe_zero(self):
        self.data[-1].loc[0,['status','execution_status']]='timeout'
        self.data[-1].loc[0,'score']=0.
        with self.assertRaises(ValueError):self.report()
    def test_failed_score_suppresses_full_AP_not_common(self):
        self.fail('synthetic://file_0000');out=self.report()['primary']['domains']
        self.assertEqual(out['full_frame_pipeline']['vectors'][self.job()]['ap_completion']['status'],'suppressed_missing_scores_no_complete_queue')
        self.assertEqual(out['common_success']['population_n'],7)
        self.assertTrue(out['common_success']['vectors'][self.job()]['ap_completion']['defined_completions_exist'])
        self.assertIsNone(out['full_frame_pipeline']['raw_LR_reference_contrasts'][0]['ap_difference_envelope']['lower'])
    def test_unknown_outside_common_not_dropped_from_design(self):
        case=self.key[self.key['class'].eq('reentrancy')].iloc[0]
        self.data[5].loc[self.data[5].case_id.eq(case.case_id),'adjudicated_judgment']='unknown'
        self.fail(case.path)
        ds=self.report()['primary']['domains']
        self.assertIsNone(ds['full_frame_pipeline']['reference_positive_total']['point'])
        self.assertIsNotNone(ds['common_success']['reference_positive_total']['point'])
        self.assertEqual(ds['common_success']['selected_outside_domain_retained_n'],1)
        self.assertEqual(ds['full_frame_pipeline']['reference_positive_total']['unknown_sample_in_domain_n'],1)
    def test_unsampled_files_retained_unknown_for_AP(self):
        ap=self.report()['primary']['domains']['full_frame_pipeline']['vectors'][self.job()]['ap_completion']
        self.assertEqual(ap['n'],8);self.assertEqual(ap['unknown_count'],4)
        self.assertEqual(len(ap['lower_completion']),8)
    def test_all_observed_negatives_keep_undefined_possible(self):
        self.data[5]['adjudicated_judgment']='negative'
        out=self.report()['primary']['domains']['full_frame_pipeline']
        ap=out['vectors'][self.job()]['ap_completion']
        self.assertTrue(ap['undefined_possible']);self.assertTrue(ap['defined_completions_exist']);self.assertIsNone(ap['identified_ap'])
        pair=out['raw_LR_reference_contrasts'][0]['ap_difference_envelope']
        self.assertTrue(pair['undefined_possible']);self.assertIsNotNone(pair['lower'])
    def test_census_all_negative_AP_and_pair_have_no_numeric_value(self):
        self.data,self.key=fixture(census=True);self.data[5]['adjudicated_judgment']='negative'
        out=self.report()['primary']['domains']['full_frame_pipeline']
        ap=out['vectors'][self.job()]['ap_completion']
        self.assertFalse(ap['defined_completions_exist']);self.assertIsNone(ap['lower_ap'])
        self.assertIsNone(out['raw_LR_reference_contrasts'][0]['ap_difference_envelope']['lower'])
    def test_empty_common_domain_ranking_undefined(self):
        for path in self.data[0].path.unique():self.fail(path)
        out=self.report()['primary']['domains']['common_success']
        self.assertEqual(out['population_n'],0);self.assertFalse(out['ranking_defined'])
        self.assertIsNone(out['vectors'][self.job()]['ap_completion']['lower_ap'])
    def test_broad_secondary_not_in_primary_inventory_or_common_set(self):
        self.data,self.key=fixture(broad=True);out=self.report()
        self.assertTrue(out['secondary_broad_slither']['excluded_from_primary_common_domain'])
        self.assertEqual(len(out['primary']['domains']['common_success']['vectors']),13)
        self.assertNotIn('slither_broad:reentrancy:0',out['primary']['coverage'])
    def test_broad_status_or_union_mismatch_rejected(self):
        self.data,self.key=fixture(broad=True)
        mask=self.data[-1].job_id.eq('slither_broad:reentrancy:0')&self.data[-1].path.eq('synthetic://file_0000')
        self.data[-1].loc[mask,'score']=0.
        with self.assertRaisesRegex(ValueError,'union'):self.report()
    def test_slither_nonbinary_score_rejected(self):
        self.data[-1].loc[self.data[-1].job_id.eq('slither:reentrancy:0'),'score']=.5
        with self.assertRaisesRegex(ValueError,'binary'):self.report()
    def test_cross_domain_AP_pair_rejected(self):
        out=self.report()['primary']['domains'];a=out['full_frame_pipeline']['vectors'][self.job()]['ap_completion'].copy();b=a.copy();b['domain_id']='different'
        with self.assertRaises(ValueError):r.ap_difference_envelope(a,b)
    def test_exploratory_explicit_audit_complete_and_only12_displayed_pairs(self):
        out=self.report(include_exploratory=True,replicates=16)
        for name,domain in out['exploratory']['domains'].items():
            self.assertEqual(len(domain['raw_LR_reference_contrasts']),12)
            self.assertEqual(len(out['engine_audit']['raw_output']['domains'][name]['paired_differences']),78)
            self.assertFalse(domain['vectors'][self.job()]['AP']['interval_coverage_validated'])
    def test_unknown_exploratory_invalid_replicates_not_dropped(self):
        self.data[5].loc[0,'adjudicated_judgment']='unknown'
        out=self.report(include_exploratory=True,replicates=16)['exploratory']['domains']['full_frame_pipeline']
        ap=out['vectors'][self.job()]['AP'];self.assertIsNone(ap['percentile_range']);self.assertEqual(ap['invalid_replicates'],16)
    def test_count_override_requires_synthetic_profile(self):
        with self.assertRaisesRegex(ValueError,'synthetic'):
            r.report_class(*self.data,'reentrancy',case_manifest=self.key,expected_files=8,expected_sample_cases=8)
    def test_inactive_production_admission_opens_nothing(self):
        with patch.object(Path,'open',side_effect=AssertionError('No reads')):
            out=r.production_admission('/nonexistent',reviewer_name='not authentication',approved=True)
        self.assertFalse(out['admitted']);self.assertEqual(out['files_opened'],0)

class LinearDesignTests(unittest.TestCase):
    def sample(self,N=4,n=2):
        sample=pd.DataFrame({'case_id':[f'fictional{i}' for i in range(n)],'source_id':'toy','class':'reentrancy',
          'label_status':r.review.POS,'N_h':N,'n_h':n,'inclusion_probability':n/N,'design_weight':N/n})
        allocation=sample[r.v1.STRATA+['N_h','n_h']].drop_duplicates()
        return sample,allocation
    def test_enumerated_design_variance_matches_sampling_variance(self):
        values=np.asarray([0.,1.,1.,0.]);sample,allocation=self.sample();estimates=[];variances=[]
        for ids in combinations(range(4),2):
            z=values[list(ids)];out=r.v1.ht_total(z,sample,allocation)
            estimates.append(out['estimate']);variances.append(out['design_variance_estimate'])
        self.assertAlmostEqual(np.mean(estimates),values.sum())
        self.assertAlmostEqual(np.mean(variances),np.var(estimates))
    def test_signed_unknown_endpoints_and_full_unsampled_logical_bounds(self):
        sample,allocation=self.sample();labels=np.array([np.nan,np.nan,np.nan,np.nan]);coeff=np.array([-1.,1.,-.5,.25])
        out=r.fixed_queue_ht(coeff,np.ones(4,dtype=bool),labels,sample,allocation,labels[:2],np.array([0,1]))
        self.assertIsNone(out['point']);self.assertEqual(out['endpoint_estimates']['lower']['estimate'],-2)
        self.assertEqual(out['endpoint_estimates']['upper']['estimate'],2)
        self.assertEqual(out['logical_population_bounds']['lower'],-1.5);self.assertEqual(out['logical_population_bounds']['upper'],1.25)
    def test_HT_yield_remains_unclipped_to_queue_capacity(self):
        sample,allocation=self.sample(N=10);labels=np.array([1.,1.]+[np.nan]*8);q=np.array([1.,1.]+[0.]*8)
        out=r.fixed_queue_ht(q,np.ones(10,dtype=bool),labels,sample,allocation,labels[:2],np.array([0,1]))
        self.assertEqual(out['point']['estimate'],10);self.assertEqual(out['logical_population_bounds']['upper'],2)
        self.assertEqual(out['point']['design_variance_estimate'],0);self.assertFalse(out['variance_zero_means_certainty'])
    def test_sample_full_reference_mismatch_rejected(self):
        sample,allocation=self.sample()
        with self.assertRaises(ValueError):r.fixed_queue_ht(np.ones(4),np.ones(4,dtype=bool),[1,0,None,None],sample,allocation,[0,0],[0,1])

if __name__=='__main__':unittest.main()
