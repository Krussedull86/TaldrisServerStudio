# Profile-scoped RCon (0.11.2)

Stop the selected server, open RCon & players and choose Create RCon in profile folder. The proposed UDP port is game port + 3. A collision with the game/query ports is rejected. Enter a 12–64 character ASCII password without spaces, or leave it blank to retain an existing password/generate a random one.

The file is created as <profiles>/BattlEye/BEServer_x64.cfg with RConPassword, RConPort and RestrictRCon 0. Existing files are backed up. The stock BattlEye server DLL is copied there if available. The selected profile's launch command explicitly points -BEpath to that folder. An existing manual -BEpath must be removed first. Restart DayZ to apply; setup is unavailable while the server runs. The owned automatic Windows UDP firewall rule includes the configured RCon port. Router forwarding is separate; Android connects to the HTTPS gateway and does not need direct RCon access.

References:
https://community.bohemia.net/wiki/DayZ:Server_Configuration
https://www.battleye.com/support/documentation/
https://cftools.com/help/technical/battleye-rcon
