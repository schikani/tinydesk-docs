# TinyDesk <small>v0.1.1 · Developer preview</small>

> A tiny board. A real desktop. Inside your terminal.

<p class="cover-cta">
  <a class="primary" href="install/">Install / Download</a>
  <a href="#/guide/getting-started">Build from source</a>
  <a href="https://github.com/schikani/tinydesk">GitHub</a>
</p>

<div class="cover-shots">
  <figure>
    <picture>
      <source media="(prefers-reduced-motion: reduce)" srcset="media/desktop-demo-esp32.png">
      <img src="media/desktop-demo-esp32.gif" alt="Editor, Files, System Monitor and Terminal opened, dragged and resized side by side on a physical ESP32, then About">
    </picture>
    <figcaption><b>TinyDesk Desktop</b>: four apps side by side on a real ESP32 · <a href="media/desktop-demo-esp32.mp4" target="_blank" rel="noopener">Watch the video</a></figcaption>
  </figure>
  <figure>
    <img src="images/terminal.png" alt="TinyDesk Shell 0.1.1 on an ESP32 serial console: the welcome banner, then version, ls, shell arithmetic and heap">
    <figcaption><b>TinyDesk Shell</b>: the same shell on its own, on a serial console</figcaption>
  </figure>
</div>

<p class="capture-note">Captured from an ESP32 over USB serial at normal speed. The board runs the desktop.</p>

- Windows, taskbar, start menu, mouse, and a real shell
- Open Files, edit and save text, then run a command in Terminal
- Connect a real project with MQTT or Modbus
- Use a UTF-8 terminal with ANSI/VT cursor control and xterm mouse reporting
- Remote access is opt-in after changing the factory root password
- Portable C11 core with a four-function port layer: ports for ESP32-C6, ESP32, Linux and Windows
- TinyDesk Shell: the same shell as an app on the desktop, or on its own
