Example bench configurations for the SEE_Tester bench.

Use the package entry point in this repo to run the example config as a dry run:

    python -m SEE_Tester.scripts.run_bench SEE_Tester/bench/examples/bench_config.json

The config fields are intentionally simple. `resource` values are placeholders
— replace them with your actual VISA resource strings before connecting to
real instruments.
