# make js: minify static/script.js -> static/script.min.js
# make db: populates the SQLite database
# make dev: run Flask dev server
# make install: installs dependencies. 

.PHONY: js db dev install

# Minifies.
js: webapp/static/script.min.js

%.min.js: %.js
	npx terser $< --compress --mangle --output $@

# Populates database with free sources.
db:
	python -m citylex.populate --all-free

# Flask dev server.
dev:
	flask --app webapp.app run --debug

# Install all dependencies.
install:
	pip install -r requirements.txt
	npm install
