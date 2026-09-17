.PHONY: install install-frontend install-backend install-hooks dev dev-frontend dev-backend

install: install-frontend install-backend

install-frontend:
	cd frontend && npm install

install-backend:
	cd backend && python3 -m pip install -r requirements.txt

install-hooks:
	git config core.hooksPath .githooks

dev-frontend:
	cd frontend && npm run dev

dev-backend:
	cd backend && uvicorn app.main:app --reload

dev:
	$(MAKE) -j 2 dev-frontend dev-backend
