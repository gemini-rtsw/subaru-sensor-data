# RPM for the Subaru sensors system.
#
# Ships the two systemd units and their site config -- NOT the application,
# which lives in the container image on GHCR. Both units are pinned to the image
# tag matching this package's NVR, so `rpm -q subaru-sensor-data` tells you
# exactly what runs and `dnf downgrade` is a real rollback.
%global specver 1.0.1

# $GIT_HASH first: build_rpm.sh computes it on the host and passes it in.
# Shelling out to git alone yields "nogit" inside the builder, which would make
# the Release and the image tag disagree.
%define git_hash %(if [ -n "$GIT_HASH" ]; then echo "$GIT_HASH"; else git rev-parse --short HEAD 2>/dev/null || echo nogit; fi)

%global appimage ghcr.io/gemini-rtsw/subaru-sensor-data
%global units subaru-sensors-ioc.service subaru-sensors-web.service

Name:           subaru-sensor-data
Version:        %{specver}
Release:        1.git%{git_hash}%{?dist}
Summary:        Subaru telescope sensor data as EPICS PVs, with a web dashboard

License:        MIT
URL:            https://github.com/gemini-rtsw/subaru-sensor-data
Source0:        %{name}-%{version}.tar.gz

BuildArch:      noarch
BuildRequires:  systemd-rpm-macros
Requires:       systemd

# Deliberately NOT `Requires: /usr/bin/docker`: docker is not always installed
# from an RPM that declares that file, and an unsatisfiable dependency turns a
# working deployment into a failed `dnf install`. The units' Requires=docker.service
# catches a genuinely missing daemon at start time, where the error is legible.

%description
Exposes Subaru telescope sensor data (weather, particles, SO2) as EPICS CA and
PVA PVs, plus a web dashboard.

This package contains only the systemd units and their site configuration. The
IOC and web server run from the container image
%{appimage}:%{version}-git%{git_hash}. Installing does not pull it, so
pre-pull it as a docker-group user logged in to GHCR, then start:

    docker pull %{appimage}:%{version}-git%{git_hash}
    systemctl enable --now subaru-sensors-ioc subaru-sensors-web

If the image is missing at start, the units pull it as the `software` user,
never as root.

%prep
%autosetup

%build
for u in subaru-sensors-ioc subaru-sensors-web; do
    sed -e 's|@IMAGE@|%{appimage}:%{version}-git%{git_hash}|' deploy/$u.service.in > $u.service
    grep -q '@IMAGE@' $u.service && { echo "ERROR: placeholder not substituted in $u" >&2; exit 1; }
    grep -q '^Environment=IMAGE=%{appimage}:%{version}-git%{git_hash}$' $u.service \
        || { echo "ERROR: image pin missing or malformed in $u" >&2; exit 1; }
done

%install
for u in subaru-sensors-ioc subaru-sensors-web; do
    install -Dpm 0644 $u.service          %{buildroot}%{_unitdir}/$u.service
    install -Dpm 0644 deploy/$u.sysconfig %{buildroot}%{_sysconfdir}/sysconfig/$u
done

%post
%systemd_post %{units}

%preun
%systemd_preun %{units}

%postun
# Deliberately NOT %%systemd_postun_with_restart: on a host where the new image
# is neither pre-pulled nor pullable as `software`, an automatic restart would
# stop a working IOC and fail to start the new one. The new image takes effect on the next
# `systemctl restart`.
%systemd_postun %{units}

%files
# NOT %%config: the units carry the image tag, so an upgrade must overwrite them.
%{_unitdir}/subaru-sensors-ioc.service
%{_unitdir}/subaru-sensors-web.service
%config(noreplace) %{_sysconfdir}/sysconfig/subaru-sensors-ioc
%config(noreplace) %{_sysconfdir}/sysconfig/subaru-sensors-web

%changelog
* Wed Sep 30 2026 Hawi Stecher <hawi.stecher@noirlab.edu> - 1.0.1-1
- Units pull the image as the `software` user, and only when it is missing:
  root on production hosts has no GHCR credentials. Without `software` they
  say how to pull it by hand.

* Tue Sep 29 2026 Hawi Stecher <hawi.stecher@noirlab.edu> - 1.0.0-1
- Package the IOC and web server as systemd units running the GHCR image.
