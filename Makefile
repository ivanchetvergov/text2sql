.PHONY: serve bench clean-logs

serve:
	uvicorn --factory src.llm_service:make_app --host 0.0.0.0 --port 8000 --reload

bench:
	python -m src.benchmark $(ARGS)

clean-logs:
	@rm -f logs/*.log
	@echo "logs cleared"
