"""Check the arithmetic behind Sentinel's recorded synthetic evidence.

Standard library only. Does not retrain the model, execute the API or verify a plant.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform

def condition_reference(vibration, temperature, quality='good'):
    if quality!='good':
        return {'health':None,'status':'unknown'}
    penalty=max(0,(vibration-1.6)*10.8)+max(0,(temperature-70)*0.65)
    health=max(8,min(99,round(100-penalty)))
    return {'health':health,'status':'critical' if health<45 else 'warning' if health<75 else 'healthy'}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    tp,fp,fn,tn=100,13,0,287
    metrics={'precision':round(tp/(tp+fp),3),'recall':round(tp/(tp+fn),3),
             'f1':round(2*tp/(2*tp+fp+fn),3),'false_positive_rate':fp/(fp+tn)}
    assert (metrics['precision'],metrics['recall'],metrics['f1'])==(0.885,1.0,0.939)
    conditions=[{'vibration_mm_s':v,'temperature_degC':t,'quality':q,
                 'reference':condition_reference(v,t,q)}
                for v,t,q in [(2,70,'good'),(4.5,80,'good'),(6,90,'good'),(2,70,'bad')]]
    assert [x['reference']['health'] for x in conditions]==[96,62,39,None]
    conversions=[{'raw_value':0.1,'raw_unit':'in/s','canonical_value':0.1*25.4,'canonical_unit':'mm/s'},
                 {'raw_value':158,'raw_unit':'degF','canonical_value':158*5/9-32*5/9,'canonical_unit':'degC'},
                 {'raw_value':500,'raw_unit':'kPa','canonical_value':500*.01,'canonical_unit':'bar'},
                 {'raw_value':2000,'raw_unit':'L/min','canonical_value':2000*.06,'canonical_unit':'m3/h'}]
    assert [round(x['canonical_value'],6) for x in conversions]==[2.54,70,5,120]
    report={
        'source_commit':'8c52a8a8ef78457a1f218638ab2bf6f27a1907a5',
        'recorded_at_utc':datetime.now(timezone.utc).isoformat(),
        'environment':{'python':platform.python_version(),'platform':platform.system()},
        'scope':'Independent arithmetic consistency and boundary illustrations from committed source and recorded synthetic metrics. Not application execution or model retraining.',
        'source_paths':['backend/intelligence.py','backend/sensor_events.py','backend/projections.py','docs/evidence/synthetic-model-evaluation.json'],
        'synthetic_model_record':{'training_samples':1500,'evaluation_samples':400,'normal':300,'abnormal':100,
            'derived_confusion_matrix':{'true_positive':tp,'false_positive':fp,'false_negative':fn,'true_negative':tn},
            'confusion_matrix_basis':'Derived from the documented 300 normal / 100 abnormal holdout, 13 false positives and recorded recall 1.0.',
            'recomputed_metrics':metrics,'interpretation':'The recorded metrics are arithmetically consistent. No conclusion about real equipment quality follows.'},
        'condition_index_examples':conditions,
        'unit_conversion_examples':conversions,
        'alignment_boundary_examples':[{'observation_offsets_seconds':[0,1,3,5],'spread_seconds':5,'within_5_second_spread':True},
            {'observation_offsets_seconds':[0,1,3,5.001],'spread_seconds':5.001,'within_5_second_spread':False}],
        'alignment_limit':'Spread alone is insufficient: latest good events, valid conversions, current sensor freshness, non-future observation times and a newer-than-current frame are also required.',
        'not_executed':['Model training/inference','Application backend tests','Sensor API','PostgreSQL','MQTT','CMMS vendor','Browser','Cloud','Plant control']
    }
    rendered=json.dumps(report,indent=2)+'\n'
    if args.output:args.output.write_text(rendered,encoding='utf-8')
    else:print(rendered,end='')

if __name__=='__main__':main()
