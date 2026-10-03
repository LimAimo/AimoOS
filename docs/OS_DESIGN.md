# AimoOS 0.1.0 implementation brief

Confirmed with the user on 2026-10-03:

- Bootable x86-64 Linux experience in a virtual machine, based on Ubuntu.
- Self-written native Qt desktop and basic applications.
- AimoChat paper/ink/neutral/terracotta design, light and dark themes.
- Centered bottom taskbar and start menu, familiar Windows-style operations.
- Real window dragging, resizing, minimize, maximize, edge snapping and Alt+Tab.
- First-run account setup, multiple Linux users, login, locking and persistent user data.
- File manager, terminal, settings, notes, calculator and real web browsing.
- Real third-party Linux applications integrated into task switching.
- Daily office workflows: LibreOffice Writer/Calc/Impress, PDF/images and Chinese input.
- Original restrained paper-composition wallpaper; matching dark composition.
- Continuous restrained motion; no additional feature expansion in this version.
- Source belongs in a separate user-owned AimoOS GitHub repository.
- Deliver genuine running-system screenshots after verifying the booted image.

## Native adaptation

Qt replaces DOM/CSS mechanics. Shared native controls own their animation,
current geometry and pointer handling. Segmented labels are drawn twice, with
the inverted text layer clipped to the moving indicator's real rectangle.
There is one native control implementation used by all built-in applications.

Linux accounts and password verification are separate from GUI presentation.
The window-manager/display infrastructure is reused to support arbitrary Linux
applications; the shell, launch experience, controls and built-ins are authored
for this project. Desktop content stays flat, with actual floating windows
allowed subtle depth so overlapping application boundaries remain readable.

Version 0.2 adds a Chinese BIOS installer and VMware VMX/VMDK packaging.
BIOS and SATA startup are verified with QEMU; real Windows VMware host
integration remains unverified. Native hardware, Windows executable compatibility
and an app store are future scopes.
