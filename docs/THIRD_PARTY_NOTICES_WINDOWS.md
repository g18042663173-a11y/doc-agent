# Windows Portable Third-Party Notices

The portable archive contains unmodified runtime components and Python packages. The source repository does not claim ownership of them.

| Component | Version | License / notice source |
| --- | --- | --- |
| Microsoft .NET runtime and WPF | 8.0.29 | MIT; bundled runtime license and third-party notices apply |
| CPython embeddable runtime | 3.12.10 | Python Software Foundation License 2.0; `runtime/python/LICENSE.txt` |
| Graphviz | 15.1.0 | Eclipse Public License 1.0; Graphviz distribution notices apply |
| Flask / Werkzeug / Jinja2 / Click / ItsDangerous / Blinker / MarkupSafe | locked in `requirements-win312.lock` | BSD/MIT licenses from each wheel metadata |
| Pydantic / pydantic-core / annotated-types / typing-inspection | locked in `requirements-win312.lock` | MIT licenses from each wheel metadata |
| python-docx / python-pptx / openpyxl / Pillow / lxml / XlsxWriter / graphviz | locked in `requirements-win312.lock` | licenses from each wheel metadata |

The package builder extracts each installed wheel's `METADATA` license fields into `runtime-manifest.json`. Development-only xUnit, FlaUI and Playwright dependencies are not copied into the production archive.
