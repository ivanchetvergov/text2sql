.PHONY: serve-llama serve-api all

serve-llama:
	ollama serve

serve-api:
	python -m text2sql.llm_service

all: serve-llama & serve-api
	@echo "services started"
