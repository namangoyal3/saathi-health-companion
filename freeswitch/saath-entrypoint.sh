#!/bin/sh
# Replacement for safarov/freeswitch upstream entrypoint.
# Identical logic, plus ESL_PASSWORD injection after vanilla copy.
set -e

if [ -z "$SOUND_RATES" ] || [ -z "$SOUND_TYPES" ]; then
    echo "Environment variables 'SOUND_RATES' or 'SOUND_TYPES' not defined. Skipping sound files checking."
fi

if [ "$EPMD" = "true" ]; then
    /usr/bin/epmd -daemon
fi

if [ ! -f "/etc/freeswitch/freeswitch.xml" ]; then
    SIP_PASSWORD=$(cat /dev/urandom | tr -dc _A-Z-a-z-0-9 | head -c12)
    mkdir -p /etc/freeswitch
    cp -arf /usr/share/freeswitch/conf/vanilla/* /etc/freeswitch/
    sed -i "s/default_password=.*\?/default_password=$SIP_PASSWORD\"/" /etc/freeswitch/vars.xml
    echo "New FreeSwitch password for SIP calls set to '$SIP_PASSWORD'"

    # Inject runtime ESL password so fs_cli and the Python ESL client agree.
    ESL_PW="${ESL_PASSWORD:-change-me-esl}"
    sed -i "s|<param name=\"password\" value=\"[^\"]*\"/>|<param name=\"password\" value=\"${ESL_PW}\"/>|" \
        /etc/freeswitch/autoload_configs/event_socket.conf.xml
    echo "FreeSWITCH ESL password set from ESL_PASSWORD env var."

    # Allow RFC1918 addresses (covers Docker bridge 172.x.x.x / host 10.x.x.x / LAN 192.168.x.x).
    # FreeSWITCH defaults to loopback-only when apply-inbound-acl is absent; that blocks Docker.
    sed -i 's|<!--<param name="apply-inbound-acl" value="loopback.auto"/>-->|<param name="apply-inbound-acl" value="rfc1918.auto"/>|' \
        /etc/freeswitch/autoload_configs/event_socket.conf.xml
    echo "FreeSWITCH ESL ACL set to rfc1918.auto (Docker-friendly)."
fi

trap '/usr/bin/freeswitch -stop' SIGTERM

/usr/bin/freeswitch -nc -nf -nonat &
pid="$!"

wait $pid
exit 0
