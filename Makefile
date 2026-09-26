.PHONY: install install-frontend install-backend install-hooks dev dev-frontend dev-backend dev-assessment dev-matching dev-registry dev-scheduling

BACKEND_SERVICES := assessment matching registry scheduling

install: install-frontend install-backend

install-frontend:
	cd frontend && npm install

install-backend:
	cd backend && python3 -m pip install -e libs/kakimetch_common -r requirements-dev.txt -r scripts/requirements.txt $(foreach s,$(BACKEND_SERVICES),-r services/$(s)/requirements.txt)

install-hooks:
	git config core.hooksPath .githooks

dev-frontend:
	cd frontend && npm run dev

dev-assessment:
	cd backend/services/assessment && uvicorn app.main:app --reload --port 8001

dev-matching:
	cd backend/services/matching && uvicorn app.main:app --reload --port 8002

dev-registry:
	cd backend/services/registry && uvicorn app.main:app --reload --port 8003

dev-scheduling:
	cd backend/services/scheduling && uvicorn app.main:app --reload --port 8004

dev-backend:
	$(MAKE) -j 4 $(foreach s,$(BACKEND_SERVICES),dev-$(s))

dev:
	$(MAKE) -j 5 dev-frontend $(foreach s,$(BACKEND_SERVICES),dev-$(s))
