# make db: populates the SQLite database
# make db-celex: adds the SQLite database with CELEX data too
# make deploy: uploads assets to server
# make install: installs dependencies
# make js: minifies Javascript
# make server: local dev server at http://localhost:8000

.PHONY: db db-celex deploy install js server

db:
	python -m populate --all-free

db-celex:
	python -m populate --all-free --celex

JS_SRCS := $(filter-out app/%.min.js,$(wildcard app/*.js))
JS_MINS := $(JS_SRCS:.js=.min.js)
 
app/%.min.js: app/%.js
	npx terser $< --compress --mangle --output $@
 
js: $(JS_MINS)

server:
	npx serve -l 8000 app

deploy:
	rsync -avkP \
		--include='*.min.js' \
		--exclude='*.js' \
		app/ wellformedness:~/public_html/citylex/

install:
	pip install -r requirements.txt
	npm install
