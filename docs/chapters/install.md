## 2. Installation and Setup

Plover installs like any other QGIS Python plugin. There is nothing to compile, no `pip install` step, and no configuration file to edit. This chapter covers the three ways to install it, how to confirm the installation worked, and how to enable, update, uninstall, and troubleshoot it.

Read section 2.1 first — it tells you which QGIS versions Plover will run on. Then pick **one** of sections 2.2 (plugin repository), 2.3 (ZIP file), or 2.4 (source checkout). Do not do more than one: a QGIS profile can hold only one copy of a plugin, and the later install silently replaces the earlier one.

---

### 2.1 Requirements

All of the following comes from the plugin's own `metadata.txt`.

| Item | Value | What it means for you |
|---|---|---|
| Plugin name | `Plover` | This is the name shown in the Plugin Manager and in the Processing Toolbox. |
| Version documented here | `3.2.5` | Check your installed version against this if behaviour differs from the guide. |
| `qgisMinimumVersion` | `3.22` | QGIS 3.22 (Białowieża LTR) or newer. QGIS 3.16 and older will not load it. |
| `qgisMaximumVersion` | `4.99` | Runs on the whole QGIS 3.x line and on QGIS 4.x. |
| `supportsQt6` | `True` | Works in both Qt5 builds (typical QGIS 3.x) and Qt6 builds (QGIS 4.x). |
| `category` | `Vector` | Determines where the menu entry appears — see section 2.5.1. |
| `hasProcessingProvider` | `yes` | The Processing algorithm is registered automatically; no extra step. |
| `experimental` | `False` | You do **not** need to tick "Show also experimental plugins" to find it. |
| `deprecated` | `False` | It is a current, supported plugin. |
| `server` | `False` | It is a desktop plugin. Do not expect it to do anything on QGIS Server. |
| `license` | `MIT` | The `LICENSE` file is bundled inside the plugin package. |
| Author | Zachary Komarnisky — `zkomarnisky@oldscollege.ca` | |
| Repository / homepage | `https://github.com/Dozer3530/Plover` | |
| Bug tracker | `https://github.com/Dozer3530/Plover/issues` | |

#### 2.1.1 No external Python dependencies

Plover imports only:

- the Python standard library (`os`, `math`, `heapq`, `traceback`, `datetime`), and
- the APIs that ship inside QGIS itself (`qgis.core`, `qgis.gui`, `qgis.PyQt`).

There is no NumPy, no SciPy, no Shapely, no NetworkX, no OR-Tools. You do not need to open the OSGeo4W Shell, and you do not need administrator rights to install Python packages. If QGIS starts, Plover will run.

The solver in `tsp_core.py` deliberately has no QGIS import at all, which is why it can be unit-tested with any plain Python interpreter (see the developer notes in section 2.4.4).

#### 2.1.2 Which QGIS profile you are installing into

QGIS keeps plugins **per user profile**. If your organisation uses more than one profile (`Settings ▸ User Profiles`), installing Plover into one profile does not install it into the others. When in doubt, note which profile you are in before you start, and install into that one.

To print the folder of the profile you are currently running, open `Plugins ▸ Python Console` and run:

```python
from qgis.core import QgsApplication
print(QgsApplication.qgisSettingsDirPath())
```

The plugins folder is `python/plugins` beneath the path this prints.

---

### 2.2 Procedure A — install from the official QGIS Plugin Repository (recommended)

This is the normal route for field and agronomy staff. It needs an internet connection the first time, and it gives you automatic update notifications afterwards.

1. Start QGIS.
2. From the main menu choose **`Plugins`** ▸ **`Manage and Install Plugins…`**.
3. In the left-hand list of the Plugin Manager, click **`All`**.
4. Click into the search box at the top and type `Plover`. If nothing comes back, try `TSP` instead — Plover carries the tags `tsp`, `routing`, `optimization`, `vector`, `agriculture`, `path planning`, `field work`, `visibility graph` and `processing`, so any of those words will also find it.
5. Select the entry named **`Plover`** in the results list. Confirm the description on the right reads: "Boundary-aware Traveling Salesperson routing: shortest tour through your points, around your sloughs."
6. Check the version shown on the right-hand panel. This guide documents version `3.2.5`.
7. Click **`Install Plugin`**.
8. Wait for the progress bar to finish. The Plugin Manager moves Plover into the **`Installed`** list and ticks its checkbox automatically.
9. Click **`Close`**.
10. Go to section 2.5 and verify the installation.

You do not normally need to restart QGIS after a repository install.

**If Plover does not appear in the search results**, the most common cause is that your QGIS is older than 3.22 — the Plugin Manager hides plugins whose `qgisMinimumVersion` is above your QGIS version. Check `Help ▸ About` for your QGIS version. See also section 2.9.

**If your site blocks the plugin repository** (some corporate networks do), use Procedure B instead.

---

### 2.3 Procedure B — install from a downloaded ZIP

Use this when the machine has no access to the QGIS plugin repository, when you need to pin a specific version, or when IT distributes the ZIP internally.

1. Download the release ZIP. Official releases are published at `https://github.com/Dozer3530/Plover/releases` and are named using the pattern **`plover-vX.Y.Z.zip`** — for example `plover-v3.2.5.zip`.
2. Save the ZIP somewhere you can find it, such as your Downloads folder. **Do not unzip it.** QGIS wants the ZIP itself.
3. Start QGIS.
4. Choose **`Plugins`** ▸ **`Manage and Install Plugins…`**.
5. In the left-hand list, click **`Install from ZIP`**.
6. Click the **`…`** browse button beside the file field and select the `plover-vX.Y.Z.zip` you downloaded.
7. Click **`Install Plugin`**.
8. QGIS may display a security warning that installing a plugin from an untrusted ZIP carries risk. This is a standard warning shown for every ZIP install, not something specific to Plover. Accept it only if you obtained the ZIP from the official releases page or from your own IT distribution point.
9. When the install finishes, click **`Installed`** in the left-hand list and confirm **`Plover`** is present and its checkbox is ticked.
10. Click **`Close`**.
11. Go to section 2.5 and verify the installation.

#### 2.3.1 What is inside the ZIP

The release ZIP is built by `build_zip.ps1` and contains exactly one top-level folder, `tsp_route_generator/`, holding ten runtime files:

| File | Role |
|---|---|
| `__init__.py` | The `classFactory` entry point QGIS calls when loading the plugin |
| `metadata.txt` | Version, menu category, changelog, requirements |
| `LICENSE` | The MIT licence text (bundled since 3.2.2) |
| `icon.png` | Toolbar, menu and Processing-provider icon |
| `tsp_route_generator.py` | Menu/toolbar wiring and Processing registration |
| `tsp_route_generator_dialog.py` | The dialog: inputs, outputs, save/export |
| `route_task.py` | The `compute_route` pipeline and its background-task wrapper |
| `geometry_utils.py` | Boundary merging and visibility-graph construction |
| `tsp_core.py` | Pure-Python solver (Dijkstra, 2-opt, Or-opt) |
| `processing_provider.py` | The `plover:tsproute` Processing algorithm |

Tests, caches and development files are deliberately excluded from the release ZIP.

> **The folder name matters.** QGIS identifies an installed plugin by its folder name on disk, and Plover's folder is `tsp_route_generator` — not `plover`. This is expected and documented in `__init__.py`: renaming the folder would orphan every existing install. Do not rename it.

---

### 2.4 Procedure C — install from source (developers)

Use this if you are working on Plover itself, or need to run an unreleased branch. It is a plain file copy into the active profile's plugins folder.

#### 2.4.1 Locate the profile plugins folder

| Platform | Path pattern |
|---|---|
| Windows | `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins` |
| Windows (QGIS 4.x) | `%APPDATA%\QGIS\QGIS4\profiles\default\python\plugins` |
| macOS | `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins` |
| macOS (QGIS 4.x) | `~/Library/Application Support/QGIS/QGIS4/profiles/default/python/plugins` |
| Linux | `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins` |
| Linux (QGIS 4.x) | `~/.local/share/QGIS/QGIS4/profiles/default/python/plugins` |

Replace `default` with your profile name if you are not using the default profile. On Windows, `%APPDATA%` normally expands to `C:\Users\<you>\AppData\Roaming` — you can paste `%APPDATA%\QGIS` straight into the File Explorer address bar.

If you would rather have QGIS tell you than guess, run this in `Plugins ▸ Python Console`:

```python
import os
from qgis.core import QgsApplication
print(os.path.join(QgsApplication.qgisSettingsDirPath(), "python", "plugins"))
```

#### 2.4.2 Copy the plugin folder

1. Clone or download the repository, e.g. `git clone https://github.com/Dozer3530/Plover.git`.
2. Copy the **`tsp_route_generator`** folder from the repository root into the plugins folder from the table above. Copy the folder itself, not the repository root and not the folder's contents.
3. Confirm the resulting path looks like this (Windows example):

   ```
   %APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\tsp_route_generator\__init__.py
   ```

   `__init__.py` and `metadata.txt` must sit **directly** inside `tsp_route_generator`. If your path has an extra level — for example `…\plugins\Plover\tsp_route_generator\__init__.py` or `…\plugins\plover-v3.2.5\tsp_route_generator\__init__.py` — QGIS will not see the plugin.
4. Restart QGIS.
5. Open **`Plugins`** ▸ **`Manage and Install Plugins…`** ▸ **`Installed`** and tick the checkbox beside **`Plover`**.
6. Go to section 2.5 and verify.

Instead of copying, developers on Linux and macOS often symlink the working tree into the plugins folder so edits take effect without re-copying:

```bash
ln -s ~/GIT/Plover/tsp_route_generator \
      ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/tsp_route_generator
```

On Windows the equivalent, run from an elevated prompt, is:

```powershell
New-Item -ItemType SymbolicLink `
  -Path "$env:APPDATA\QGIS\QGIS3\profiles\default\python\plugins\tsp_route_generator" `
  -Target "C:\Users\<you>\GIT\Plover\tsp_route_generator"
```

After editing source you must restart QGIS for the change to load, unless you use the separate third-party **Plugin Reloader** plugin, which reloads a named plugin in place.

#### 2.4.3 Building a release ZIP from source

`build_zip.ps1` reads the version out of `metadata.txt`, packages only the ten runtime files listed in section 2.3.1, and writes `plover-vX.Y.Z.zip` into the repository root. Run it from the repository root:

```powershell
.\build_zip.ps1
```

It writes forward-slash entry names on purpose, so the ZIP extracts correctly on Linux and macOS as well as Windows. It fails loudly if any runtime file is missing.

#### 2.4.4 Running the tests

The pure-Python solver core has no QGIS dependency, so its tests run under any Python interpreter:

```powershell
python -m unittest tsp_route_generator.test.test_tsp_core -v
```

The integration and dialog tests need the real QGIS API, so run them through the QGIS Python launcher:

```powershell
& "C:\Program Files\QGIS 4.0.1\bin\python-qgis.bat" -m unittest discover -s tsp_route_generator/test -t . -v
```

Adjust the path to match your installed QGIS version.

---

### 2.5 Verifying the installation

After any of the three procedures, check all three access points. Each one is wired up independently in `tsp_route_generator.py`, so if only one of them is missing the fault is narrow and section 2.9 will tell you where to look.

#### 2.5.1 The menu entry

Plover declares `category=Vector` in `metadata.txt` and registers itself with `addPluginToVectorMenu`, so it lives under the **Vector** menu — not the generic Plugins menu.

Navigate to:

> **`Vector`** ▸ **`Plover`** ▸ **`Plover — Generate TSP Route`**

Hovering the entry shows the status tip **`Boundary-aware TSP route through a point layer`** in the QGIS status bar.

> **Note for anyone upgrading from 3.2.4 or earlier:** the menu entry used to sit under the **Plugins** menu. It moved to the **Vector** menu in version 3.2.5. Older documentation, screenshots and the repository README may still say "Plugins menu"; the Vector menu is correct for 3.2.5 and later.

Click the entry. A modeless dialog titled **`Plover — TSP Route`** opens. "Modeless" means you can keep using the map while it is open — that is intended behaviour, not a bug.

[[FIGURE: dialog-plain | The Plover — TSP Route dialog as it opens on a fresh installation, before any layer is chosen.]]

#### 2.5.2 The toolbar button

`initGui` also calls `addToolBarIcon`, which puts the Plover icon on the QGIS **Plugins Toolbar**. Look for the plover icon; its tooltip reads **`Plover — Generate TSP Route`**. Clicking it opens the same dialog as the menu entry.

If you cannot see it, the Plugins Toolbar may simply be hidden. Turn it on with **`View`** ▸ **`Toolbars`** ▸ **`Plugins Toolbar`** (tick it). Toolbars can also be dragged off-screen or collapsed into the `»` overflow arrow at the end of a toolbar row.

#### 2.5.3 The Processing Toolbox entry

Because `metadata.txt` sets `hasProcessingProvider=yes` and `initGui` calls `initProcessing`, Plover registers a Processing provider as soon as the plugin loads.

1. Open the Processing Toolbox with **`Processing`** ▸ **`Toolbox`** (or press `Ctrl+Alt+T`).
2. In the tree, find the provider group named **`Plover`**.
3. Expand it. It contains one algorithm: **`Boundary-aware TSP route`**.

The identifiers a technical user needs:

| Item | Value | Source |
|---|---|---|
| Provider id | `plover` | `PloverProcessingProvider.id()` |
| Provider display name | `Plover` | `PloverProcessingProvider.name()` |
| Algorithm name | `tsproute` | `PloverRouteAlgorithm.name()` |
| Algorithm display name | `Boundary-aware TSP route` | `PloverRouteAlgorithm.displayName()` |
| Fully qualified algorithm id | `plover:tsproute` | provider id + algorithm name |


To confirm registration from the QGIS Python Console (`Plugins ▸ Python Console`):

```python
import processing
processing.algorithmHelp("plover:tsproute")
```

If the algorithm is registered, this prints its description and its full parameter list. If it raises an error or prints nothing useful, the provider is not registered — see section 2.9.

You can also list every loaded plugin by folder name; Plover appears as `tsp_route_generator`:

```python
import qgis.utils
print(sorted(qgis.utils.plugins.keys()))
```

#### 2.5.4 A one-minute smoke test

If you want proof that the routing engine itself works, not just that the menus exist:

1. Load, or draw, a point layer with at least two points in a **projected** CRS (UTM, for example). Plover rejects geographic CRS such as EPSG:4326 outright, so a lat/long layer will produce an error message rather than a route — that is by design, not an installation problem.
2. Open **`Vector`** ▸ **`Plover`** ▸ **`Plover — Generate TSP Route`**.
3. Choose your layer in **`Points to visit:`**. Leave **`Boundary layer:`** empty — with no boundary Plover solves a plain straight-line tour, which is the fastest way to prove the install.
4. Click **`Run`**.
5. Within a second or two the status line should change from `Ready.` to a `Done — …` message, **`Total distance:`** should fill in, and a memory layer named **`Plover route`** should appear in the Layers panel (plus **`Plover visit order`** if the numbered-layer checkbox is ticked).

If that works, the installation is complete and correct.

---

### 2.6 Enabling and disabling the plugin

An installed plugin only loads when its checkbox is ticked. A plugin can end up unticked because someone disabled it deliberately, or because a previous load error caused QGIS to switch it off.

To enable:

1. **`Plugins`** ▸ **`Manage and Install Plugins…`**.
2. Click **`Installed`** in the left-hand list.
3. Find **`Plover`** in the list. (The list is sorted by display name, so look under P, not under T for `tsp_route_generator`.)
4. Tick the checkbox beside it.
5. Click **`Close`**.

The Vector menu entry, the toolbar button and the Processing provider all appear immediately — they are created in `initGui`, which runs when the plugin is enabled.

To disable, untick the same checkbox. `unload` runs and removes all three: the Vector menu entry, the toolbar icon and the `Plover` Processing provider. Any open Plover dialog is closed, and if a route is still computing in the background it is cancelled. Disabling does not delete the plugin files and does not touch your saved preferences.

---

### 2.7 Updating to a new version

#### 2.7.1 If you installed from the plugin repository

1. **`Plugins`** ▸ **`Manage and Install Plugins…`**.
2. Click **`Upgradable`** in the left-hand list. QGIS checks the repository on startup by default, so a new Plover release usually announces itself with a message-bar notification.
3. Select **`Plover`**.
4. Click **`Upgrade Plugin`**.
5. Restart QGIS if prompted.

#### 2.7.2 If you installed from a ZIP

Repeat Procedure B (section 2.3) with the newer `plover-vX.Y.Z.zip`. Installing from ZIP over an existing install replaces it; you do not need to uninstall first.

#### 2.7.3 If you installed from source

Pull the latest commits and copy the `tsp_route_generator` folder over the old one, then restart QGIS. If you symlinked the working tree, a `git pull` plus a QGIS restart is enough.

#### 2.7.4 After any upgrade

- Confirm the version in **`Plugins`** ▸ **`Manage and Install Plugins…`** ▸ **`Installed`**; the installed version is shown alongside the plugin.
- Read the `changelog` section of `metadata.txt`, or the release notes on GitHub. Behaviour genuinely moves between versions: the menu moved from Plugins to Vector in 3.2.5, the boundary became optional in 3.2.0, the "Points outside boundary" choice arrived in 3.1.0, and background/cancellable runs plus the `plover:tsproute` algorithm arrived in 3.0.0.
- Your saved preferences survive upgrades (section 2.8.1), so the dialog reopens with the buffer, round-trip and outside-mode settings you last used.

---

### 2.8 Uninstalling

1. **`Plugins`** ▸ **`Manage and Install Plugins…`**.
2. Click **`Installed`**.
3. Select **`Plover`**.
4. Click **`Uninstall Plugin`** and confirm.

This removes the menu entry, the toolbar icon and the Processing provider, and deletes the `tsp_route_generator` folder from the profile's plugins directory.

For a source install made by copying or symlinking the folder yourself, the Plugin Manager may not offer **`Uninstall Plugin`**. In that case close QGIS and delete (or unlink) the `tsp_route_generator` folder from the plugins path in section 2.4.1 by hand.

#### 2.8.1 What uninstalling does *not* remove

Plover remembers a few dialog preferences using QGIS's own settings store (`QgsSettings`), which lives in the user profile, not in the plugin folder. Uninstalling the plugin leaves these keys behind:

| Settings key | What it remembers |
|---|---|
| `plover/buffer` | Last value of **`Boundary buffer:`** (defaults to `0.5`) |
| `plover/round_trip` | Last state of **`Return to start (round trip)`** (defaults to ticked) |
| `plover/order_layer` | Last state of **`Also create a numbered visit-order layer`** (defaults to ticked) |
| `plover/outside_mode` | Last value of **`Points outside boundary:`** — stored as `fail` or `skip` (defaults to `fail`) |
| `plover/last_save_dir` | The folder last used by **`Save Route…`** |

These are harmless, take up a trivial amount of space, and are picked up again if you reinstall. If you genuinely want a clean slate, delete the `plover/*` keys through **`Settings`** ▸ **`Options`** ▸ **`Advanced`**, or simply create a fresh user profile.

Output layers Plover created (`Plover route`, `Plover visit order`) are ordinary QGIS memory layers. They belong to your project, not to the plugin, and are unaffected by uninstalling. Files you exported with **`Save Route…`** are likewise untouched.

---

### 2.9 Installation troubleshooting

#### 2.9.1 Plover does not appear in the Plugin Manager at all

| Check | Fix |
|---|---|
| Your QGIS version is older than 3.22 | Check `Help ▸ About`. The Plugin Manager hides plugins whose `qgisMinimumVersion` exceeds your QGIS version. Upgrade QGIS; there is no build of Plover for 3.16 or earlier. |
| You searched the wrong list | Repository installs: search under **`All`**. Already-installed copies: look under **`Installed`**. |
| You searched for the folder name | Search for `Plover`, not `tsp_route_generator`. The Plugin Manager lists the display name. |
| Repository is unreachable | In the Plugin Manager, open **`Settings`** and press **`Reload Repository`**. If your network blocks it, use Procedure B (ZIP). |
| Wrong profile | You may have installed into a different user profile. Check `Settings ▸ User Profiles`, or print the profile path as shown in section 2.1.2. |

#### 2.9.2 Source or manual install: nothing shows up after restarting QGIS

Almost always a folder-depth problem. The file `__init__.py` must be **exactly two levels** below the profile folder, at `…/python/plugins/tsp_route_generator/__init__.py`.

| Symptom | Cause | Fix |
|---|---|---|
| Path is `…/plugins/plover-v3.2.5/tsp_route_generator/__init__.py` | You unzipped the release ZIP into the plugins folder instead of using **Install from ZIP** | Move the inner `tsp_route_generator` folder up one level and delete the wrapper folder |
| Path is `…/plugins/Plover/tsp_route_generator/__init__.py` | You copied the whole repository instead of just the plugin folder | Move `tsp_route_generator` up one level |
| Path is `…/plugins/tsp_route_generator/tsp_route_generator/__init__.py` | The folder was copied into itself | Remove the extra level |
| Folder renamed to `plover` or similar | QGIS identifies plugins by folder name | Rename it back to `tsp_route_generator` exactly |
| Files copied but QGIS still not restarted | Plugins are discovered at startup | Restart QGIS |

#### 2.9.3 Plover is listed but the checkbox will not stay ticked

That is QGIS disabling a plugin that raised an error while loading. Open **`View`** ▸ **`Panels`** ▸ **`Log Messages`** and read the **`Plugins`** tab for the traceback. The two usual causes are an incomplete copy (one of the ten runtime files missing) and a QGIS version below 3.22. Re-copy the full folder, or upgrade QGIS.

#### 2.9.4 The plugin is enabled but the menu entry is missing

| Check | Fix |
|---|---|
| You are looking under the **Plugins** menu | From version 3.2.5 the entry lives under **`Vector`** ▸ **`Plover`** ▸ **`Plover — Generate TSP Route`**. Older notes and the README may still say Plugins. |
| You are running 3.2.4 or older | On those versions the entry *is* under the Plugins menu. Check your installed version, and upgrade if you want the documented layout. |
| The Vector menu is short or missing entries | Some QGIS setups hide menus per profile/customisation. Check `Settings ▸ Interface Customization` and make sure menu customisation is not hiding the entry. |
| Checkbox is unticked | Section 2.6. The menu entry only exists while the plugin is enabled. |

The toolbar button is registered by the same code as the menu entry, so if the toolbar icon is present but the menu entry is not, suspect interface customisation rather than the plugin.

#### 2.9.5 The toolbar button is missing

Turn the toolbar back on with **`View`** ▸ **`Toolbars`** ▸ **`Plugins Toolbar`**. If the toolbar is visible but crowded, the Plover icon may be hidden behind the `»` overflow arrow at the right-hand end of the toolbar row. As a fallback, the menu entry always does the same thing as the button.

#### 2.9.6 The Processing Toolbox has no Plover provider

| Check | Fix |
|---|---|
| The Toolbox panel is closed | **`Processing`** ▸ **`Toolbox`**, or `Ctrl+Alt+T` |
| The core Processing plugin is disabled | **`Plugins`** ▸ **`Manage and Install Plugins…`** ▸ **`Installed`**, tick **`Processing`**. Plover's provider cannot register if Processing itself is not running. |
| Plover itself is disabled | The provider is added in `initGui`. A disabled plugin registers nothing. Tick Plover (section 2.6). |
| A search filter is active | Clear the Toolbox's search box; a stale filter hides whole providers. |
| Providers hidden in options | **`Settings`** ▸ **`Options`** ▸ **`Processing`** ▸ **`Providers`**, and make sure **`Plover`** is activated. |
| Just installed, provider still absent | Restart QGIS, then re-check with `processing.algorithmHelp("plover:tsproute")` from the Python Console. |

#### 2.9.7 Where to look when something else goes wrong

Plover writes its own diagnostics to a dedicated log tab. Open **`View`** ▸ **`Panels`** ▸ **`Log Messages`** and select the **`Plover`** tab. Reprojection notices, boundary repairs, skipped features, points outside the boundary and full tracebacks for unexpected failures all land there. The **`Plugins`** tab in the same panel is the place to look for load-time errors instead.

If a problem survives all of the above, raise it at `https://github.com/Dozer3530/Plover/issues`, and include your QGIS version (`Help ▸ About`), your operating system, the Plover version from the Plugin Manager, and the relevant text from the `Plover` and `Plugins` log tabs.