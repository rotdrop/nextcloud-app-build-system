# Makefile fragment in order to tweak composer dependencies not to be
# in conflict with CORE/3rdparty

ifeq (1, $(NO_STDOUT))
POSTFIX = 1>&2
endif

composer.json: composer.json.in
	cp composer.json.in composer.json

stamp.composer-core-versions: composer.lock
	date > $@

composer.lock: DRY:=
composer.lock: composer.json composer.json.in
	echo '$(POSTFIX)'
	rm -f composer.lock $(POSTFIX)
	$(COMPOSER) install $(COMPOSER_OPTIONS) $(POSTFIX)
	env DRY=$(DRY) $(DEV_LIB_DIR)/scripts/tweak-composer-json.sh "$(ABSSRCDIR)" $(POSTFIX) || {\
 rm -f composer.lock;\
 $(COMPOSER) install $(COMPOSER_OPTIONS);\
} $(POSTFIX)

composer-download:
	mkdir -p $(BUILD_TOOLS_DIR) $(POSTFIX)
	curl -sS https://getcomposer.org/installer | php $(POSTFIX)
	mv composer.phar $(BUILD_TOOLS_DIR) $(POSTFIX)
.PHONY: composer-download

composer: stamp.composer-core-versions ## Install/update the composer dependencies, fetch composer if missing
	$(COMPOSER) install $(COMPOSER_OPTIONS) $(POSTFIX)
.PHONY: composer

composer-suggest: ## Display the composer suggestions
	@echo -e "\n*** Regular Composer Suggestions ***\n"
	$(COMPOSER) suggest --all
.PHONY: composer-suggest
