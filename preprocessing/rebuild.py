"""Run the recorded pipeline in its original layout. No model training."""
import argparse,pathlib,subprocess,sys
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.parse_args()
    root=pathlib.Path(__file__).resolve().parent
    if (root/'构造general数据集').exists():raise SystemExit('Build directory already exists; use a fresh checkout to avoid overwriting a prior build.')
    scripts=['download_general.py','build_general.py','validate_general.py','download_batch2.py','build_batch2.py','validate_batch2.py','review_batch2_samples.py','finalize_batch2.py','numeric_precision.py','clean_numeric_precision.py']
    for name in scripts:
        print(f'Running {name}',flush=True)
        subprocess.run([sys.executable,str(root/'work'/name)],cwd=root,check=True)
if __name__=='__main__':main()
