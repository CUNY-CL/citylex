# make db: populates the SQLite database
# make db-celex: adds the SQLite database with CELEX data too
# make install: installs dependencies
# make js: minifies Javascript
# make serve: local dev server

.PHONY: db db-celex install js serve

db:
	python -m populate --all-free

db-celex:
	python -m populate --all-free --celex

JS_SRCS := $(filter-out app/%.min.js,$(wildcard app/*.js))
JS_MINS := $(JS_SRCS:.js=.min.js)
 
app/%.min.js: app/%.js
	npx terser $< --compress --mangle --output $@
 
js: $(JS_MINS)

# Tests server locally at http://localhost:8000.
server:
	npx serve -l 8000 app

install:
	pip install -r requirements.txt
	npm install
