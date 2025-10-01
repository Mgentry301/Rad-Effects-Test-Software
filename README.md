Bench scaffolding for Rad-Effects-Test-Software

Run the example using the canonical package under `SEE_Tester`:

    python -m SEE_Tester.scripts.run_bench SEE_Tester/bench/examples/bench_config.json

The `SEE_Tester/bench` package contains adapters, standalone instrument
drivers, a CSV recorder, and an example runner. Extend the runner and
device logic to wire your product-specific register reads.

Dependencies
------------
Install runtime dependencies before connecting to real instruments:

    python -m pip install -r requirements.txt

