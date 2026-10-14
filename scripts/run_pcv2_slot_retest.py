"""User-authorized fresh run after native mount repair; preserve the failed first run."""
import run_pcv2_full_20260928 as runner

runner.OUT=runner.common.ROOT/'reports/pcv2-full-20260928/r02'
runner.ARGS=dict(runner.ARGS,run_key='pcv2-cap-user-full-20260928-r02')

if __name__=='__main__':runner.main()
