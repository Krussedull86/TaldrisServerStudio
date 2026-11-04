# CruzDoodelZ Server Studio 0.9.1

- SteamCMD: reset the frozen application DLL search directory during external startup and remove bundled runtime paths from the child environment; restore the host environment afterward.
- Answer PTY cursor/device queries, report console read errors and handle child exit when a console backend does not send EOF.
- Automatically fetch a missing SteamCMD executable for login/install/download jobs. Reject damaged existing executables with a specific message.
- Preserve download confirmations independently of the scrolling console. Recognize already-up-to-date server confirmations, normalize Workshop IDs and include missing items / Steam errors in failure messages.
- Explicit cancellation prevents deployment and server startup after a cancelled download. Reader threads keep a reference to their own process and stop during cleanup.
- Agent-backed console now shows login/download stages, elapsed time and progress.
- Overview action buttons wrap and retain at least 40 px height. The overview and navigation scroll on smaller windows.
- CDS application icon embedded in EXE, application windows and installer shortcuts; include winpty runtime resources in packaging.

Validation: Python syntax compilation and an offscreen window preview at 1000 x 650. Start/stop buttons retained 40 px height. Automated test suites were not run, as requested. A live Steam login, Steam Guard and DayZ download on the user's Windows machine remain to be verified.
