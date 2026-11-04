# Shared app configuration for setup and standalone translation extraction.
ifndef _APP_BUILD_SCOPED_VENDOR_INCLUDED
_APP_BUILD_SCOPED_VENDOR_INCLUDED := 1

ABSSRCDIR ?= $(CURDIR)
APP_INFO = $(ABSSRCDIR)/appinfo/info.xml
XPATH := $(shell command -v xpath 2> /dev/null)
ifeq ($(XPATH),)
$(error The xpath binary could not be found, it is needed to parse $(APP_INFO))
endif

SCOPED_NAMESPACE_POSTFIX := $(strip $(shell $(XPATH) -q -e '/info/scopednamespace/text()' "$(APP_INFO)"))
ifneq ($(.SHELLSTATUS),0)
$(error Cannot read scopednamespace from $(APP_INFO))
endif
ifeq ($(SCOPED_NAMESPACE_POSTFIX),)
$(error $(APP_INFO) must declare a nonempty scopednamespace)
endif

SCOPED_VENDOR_SUFFIX := $(shell printf '%s' '$(SCOPED_NAMESPACE_POSTFIX)' | LC_ALL=C tr '[:upper:]' '[:lower:]')
ifeq ($(wildcard $(ABSSRCDIR)/composer-$(SCOPED_VENDOR_SUFFIX).json),)
$(error Required Composer manifest $(ABSSRCDIR)/composer-$(SCOPED_VENDOR_SUFFIX).json is missing)
endif

endif
