FROM safarov/freeswitch

# Fix IPv6 binding failure in ARM64 / non-IPv6 environments.
# The vanilla config binds ESL to :: which fails with "Cannot get information
# about IP address ::" on ARM64 emulation. Patch the source so the entrypoint
# copies the fixed version into /etc/freeswitch/.
RUN sed -i \
    's|<param name="listen-ip" value="::"/>|<param name="listen-ip" value="0.0.0.0"/>|' \
    /usr/share/freeswitch/conf/vanilla/autoload_configs/event_socket.conf.xml

# Replacement entrypoint: same as upstream but injects ESL_PASSWORD at runtime
# (upstream entrypoint hard-codes "ClueCon" and provides no substitution hook).
COPY saath-entrypoint.sh /saath-entrypoint.sh
RUN chmod +x /saath-entrypoint.sh
ENTRYPOINT ["/saath-entrypoint.sh"]
