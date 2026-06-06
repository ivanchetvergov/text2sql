.PHONY: serve bench clean-logs

serve:
	$(MAKE) -C llm serve-api

bench:
	$(MAKE) -C llm bench

clean-logs:
	$(MAKE) -C llm clean-logs
