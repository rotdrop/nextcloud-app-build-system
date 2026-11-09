# Opt-in phpDocumentor target. Include explicitly from the app Makefile
# AFTER app.mk:
#
#   include $(DEV_LIB_DIR)/makefile/phpdoc.mk
#
# The `doc` target is NOT defined here, apps define it themselves.
#
# Variables:
#
#   DOC_BUILD_DIR          documentation output base ($(ABSBUILDDIR)/artifacts/doc)
#   PHPDOC                 phpDocumentor binary (/opt/phpDocumentor/bin/phpdoc)
#   PHPDOC_GRAPHS          true/false, class graphs are slow, default false
#   PHPDOC_TEMPLATE        template arguments, e.g. --template=clean
#   PHPDOC_SETTINGS        extra settings, e.g. "--setting guides.enabled=true"
#   PHPDOC_DIRS            source directories (lib tests/phpunit), relative to $(SRCDIR)
#   PHPDOC_PREREQ_TARGET   target made before running phpdoc (dev-setup)
#   PHPDOC_HTML            output directory ($(DOC_BUILD_DIR)/phpdoc/)
#   PHPDOC_PLANTUML_BIN, PHPDOC_PLANTUML_ARGUMENTS,
#   PHPDOC_PLANTUML_TIMEOUT_SECONDS
#                          exported to phpDocumentor (the timeout env var is
#                          PHPDOC_PLANTUML_TIMEOUT_SECONDS)

DOC_BUILD_DIR ?= $(ABSBUILDDIR)/artifacts/doc

PHPDOC ?= /opt/phpDocumentor/bin/phpdoc
export PHPDOC_PLANTUML_BIN ?= $(shell which plantuml 2> /dev/null)
# The default of phpdoc -Playout=smetana errors out
export PHPDOC_PLANTUML_ARGUMENTS ?=
# The plantuml default layout engine dot may take hours, therefore
# graphs are disabled by default.
export PHPDOC_PLANTUML_TIMEOUT_SECONDS ?= 14400
PHPDOC_GRAPHS ?= false
PHPDOC_TEMPLATE ?=
PHPDOC_SETTINGS ?=
PHPDOC_DIRS ?= lib tests/phpunit
PHPDOC_PREREQ_TARGET ?= dev-setup
PHPDOC_HTML ?= $(DOC_BUILD_DIR)/phpdoc/

phpdoc: $(PHPDOC_HTML)/index.html ## Run phpDocumentor
.PHONY: phpdoc

# The directory arguments must be relative paths, otherwise funny things
# are happening.
$(PHPDOC_HTML)/index.html: $(APP_BUILD_HASH) $(MAKEFILE_DEP)
	$(MAKE) $(PHPDOC_PREREQ_TARGET)
	rm -rf $(PHPDOC_HTML)
	mkdir -p $(PHPDOC_HTML)
	$(PHPDOC) run \
 $(PHPDOC_TEMPLATE) \
 $(foreach d,$(PHPDOC_DIRS),-d $(SRCDIR)/$(d)) \
 --defaultpackagename $(APP_NAME) \
 --force \
 --parseprivate \
 --visibility api,public,protected,private,internal \
 --sourcecode \
 --setting graphs.enabled=$(PHPDOC_GRAPHS) \
 $(PHPDOC_SETTINGS) \
 --cache-folder $(ABSBUILDDIR)/phpdoc/cache \
 -t $(PHPDOC_HTML)
