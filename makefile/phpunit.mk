# Opt-in PHPUnit targets. Include explicitly from the app Makefile
# AFTER app.mk:
#
#   include $(DEV_LIB_DIR)/makefile/phpunit.mk
#
# Variables (all can be overridden before or after the include, except where
# noted):
#
#   PHPUNIT_OUTPUT         output directory ($(BUILDDIR)/artifacts/tests/phpunit)
#   PHPUNIT_JUNIT_LOG      junit xml log file
#   PHPUNIT_JUNIT_LOG_HTML directory with the HTML rendering of the junit log
#   PHING_BUILD_XML        generated phing build file for the junit HTML rendering
#   PHPUNIT_CONFIG         phpunit configuration file (phpunit.xml)
#   PHPUNIT_DEPS           prerequisites of the test targets, defaults to
#                          $(PHPUNIT) $(SCOPED_VENDOR_DIR)/autoload.php $(TS_TYPES_AUTOLOAD)
#                          (the latter is empty without ts-types-files.mk)
#   PHPUNIT_ARGS           extra phpunit arguments (--display-all-issues);
#                          append with e.g. PHPUNIT_ARGS += --stop-on-failure
#   PHPCOVERAGE            php options enabling coverage (xdebug)
#
# Requires $(PHPUNIT) and $(PHING) from app.mk and the phing template
# $(SRCDIR)/vendor-bin/phing/phing-build.xml.in.

PHPUNIT_OUTPUT ?= $(BUILDDIR)/artifacts/tests/phpunit
PHPUNIT_JUNIT_LOG ?= $(PHPUNIT_OUTPUT)/junit-log.xml
PHPUNIT_JUNIT_LOG_HTML ?= $(PHPUNIT_OUTPUT)/junit-log
PHING_BUILD_XML ?= $(PHPUNIT_OUTPUT)/phing-build.xml
PHPUNIT_CONFIG ?= phpunit.xml
PHPUNIT_DEPS ?= $(PHPUNIT) $(SCOPED_VENDOR_DIR)/autoload.php $(TS_TYPES_AUTOLOAD)
PHPUNIT_ARGS ?= --display-all-issues
PHPCOVERAGE ?= -d zend_extension=xdebug.so -d xdebug.mode=coverage
PHING ?= $(ABSSRCDIR)/vendor-bin/phing/vendor/bin/phing

phpunit: dophpunit $(PHPUNIT_JUNIT_LOG_HTML)/index.html ## Run phpunit with coverage and junit log and post-process the junit log
.PHONY: phpunit

phpjunit-log: $(PHPUNIT_JUNIT_LOG_HTML)/index.html ## Post-process junit-log xml file
.PHONY: phpjunit-log

dophpunit: $(PHPUNIT_DEPS)
	$(PHP) $(PHPCOVERAGE) $(PHPUNIT)\
 -c $(PHPUNIT_CONFIG)\
 --coverage-html $(PHPUNIT_OUTPUT)/code-coverage\
 --log-junit $(PHPUNIT_JUNIT_LOG)\
 $(PHPUNIT_ARGS)
.PHONY: dophpunit

$(PHPUNIT_JUNIT_LOG):

$(PHING_BUILD_XML): $(SRCDIR)/vendor-bin/phing/phing-build.xml.in $(MAKEFILE_DEP)
	mkdir -p $(dir $@)
	sed -e 's|%BASEDIR%|$(ABSSRCDIR)|g' -e 's|%INFILE%|$(PHPUNIT_JUNIT_LOG)|g' -e 's|%OUTPUTDIR%|$(PHPUNIT_JUNIT_LOG_HTML)|g' < $< > $@

$(PHPUNIT_JUNIT_LOG_HTML)/index.html: $(PHING_BUILD_XML) $(PHPUNIT_JUNIT_LOG) $(PHING)
	mkdir -p $(PHPUNIT_JUNIT_LOG_HTML)
	$(PHING) -f $(PHING_BUILD_XML)

phpunitfilter: $(PHPUNIT_DEPS) ## Run phpunit with a filter given by PHPUNITTEST on the command line
	@if [ -z "$(PHPUNITTEST)" ]; then echo "Please add PHPUNITTEST=FILTER_EXPRESSION to the make command line" 1>&2; exit 1; fi
	$(PHP) $(PHPCOVERAGE) $(PHPUNIT) -c $(PHPUNIT_CONFIG) --no-coverage --display-all-issues --filter "$(PHPUNITTEST)"
.PHONY: phpunitfilter
