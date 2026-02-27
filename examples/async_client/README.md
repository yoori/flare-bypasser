### Example of crawling site with using AsyncClient
This way is usable for case when you need to crawl much pages on web site,
AsyncClient allow to request web site pages (it solve cloud flare protection automaticaly)
without solving challenge for each page.
It solve challenge when detect it and reuse cookies for bypass challenges after,
as result usualy you will get solving delay only once.

For use it you need to up docker and use link to it on AsyncClient construction. When using Docker with default settings, the solver is at `http://localhost:20080` (host port). If you changed `PORT` in the container, set the host port mapping accordingly and use that URL (e.g. `PORT=3000` with mapping `20080:3000` → `http://localhost:20080`).
