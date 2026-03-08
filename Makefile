.PHONY: serve-llama serve-api all clean-logs

serve-llama:
	ollama serve

serve-api:
	uvicorn --factory src.llm_service:make_app --host 0.0.0.0 --port 8000 --reload

all: serve-llama & serve-api
	@echo "services started"

clean-logs:
	@rm -f logs/*.log
	@echo "logs cleared"
