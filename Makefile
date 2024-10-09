TARGET_NAME ?= snapcast-mpris-proxy
PREFIX ?= /usr/local

SYSTEMD_SERVICE_NAME ?= $(TARGET_NAME).service
SYSTEMD_POLICY_NAME ?= $(TARGET_NAME)-policy.conf

SYSTEMD_SERVICE_PATH ?= /etc/systemd/system
SYSTEMD_POLICY_PATH ?= /etc/dbus-1/system.d

MKDIR_P ?= mkdir -p

default:
	$(info Nothing to build. Run make install.)

install-systemd: $(SYSTEMD_SERVICE_NAME)
	$(info Installing systemd service.)
	cp -u $< $(SYSTEMD_SERVICE_PATH)
	systemctl daemon-reload
	systemctl enable $(SYSTEMD_SERVICE_NAME)
	systemctl start $(SYSTEMD_SERVICE_NAME)

install-bin:
	$(info Installing via pipx.)
	pipx install --global .

install-policy: $(SYSTEMD_POLICY_NAME)
	$(info Installing D-Bus policy.)
	cp $< $(SYSTEMD_POLICY_PATH)/
	systemctl reload dbus

install: install-bin install-policy install-systemd

uninstall-systemd:
	systemctl disable $(SYSTEMD_SERVICE_NAME)
	systemctl stop $(SYSTEMD_SERVICE_NAME)
	systemctl daemon-reload
	rm -f $(SYSTEMD_SERVICE_PATH)/$(SYSTEMD_SERVICE_NAME)

uninstall: uninstall-systemd
	rm -f $(SYSTEMD_POLICY_PATH)/$(SYSTEMD_POLICY_NAME)
	pipx uninstall --global $(TARGET_NAME)