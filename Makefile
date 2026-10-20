install:
	python -m pip install -r requirements.txt

test:
	pytest -v

seed:
	python scripts/seed.py

check:
	python scripts/check_db.py

run:
	streamlit run app.py

.PHONY: install test seed check run
