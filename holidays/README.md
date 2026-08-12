# Calendarios laborales

Los festivos nacionales y autonómicos de cada año, transcritos de la fuente
oficial, con la misma disciplina que las fichas de convenio de `agreements/`:
cada cifra con su publicación, y nada inventado.

## Qué hay aquí y qué no

El art. 37.2 del Estatuto da **catorce festivos al año como máximo, dos de
ellos locales**. Los otros doce salen de una única resolución que el Ministerio
publica en el BOE hacia octubre para el año siguiente, y que recoge los
nacionales y los de cada comunidad autónoma. Eso es lo que se transcribe aquí.

**Los dos locales no están y no van a estar.** Los propone cada ayuntamiento y
los aprueba la autoridad laboral autonómica, así que acaban repartidos por medio
centenar de boletines provinciales y más de ocho mil municipios, buena parte en
PDF. No existe un registro nacional legible por máquina. Se meten a mano en cada
centro de trabajo, y el producto lo dice en vez de disimularlo.

## Cómo se usa

    python manage.py import_holidays --year 2026

Crea los días de la empresa en curso: los nacionales para todo el mundo, y los
autonómicos para los centros de esa comunidad. Un centro sin comunidad asignada
se queda solo con los nacionales, y el comando lo avisa.

Volver a ejecutarlo **reemplaza** lo importado de ese año y **no toca** los días
locales ni los que haya añadido la empresa: son los que nadie más puede
reponer.

## Añadir un año

1. Busca la resolución en el BOE. Suele llamarse «Resolución de … por la que se
   publica la relación de fiestas laborales para el año …».
2. Copia `_template.yaml` a `es/<año>.yaml`.
3. Rellena `source` con el identificador del BOE y la fecha. Sin eso no se
   puede volver al original a discutir un día.
4. Transcribe. **Sin deducir**: si una comunidad sustituye un festivo nacional,
   se anota como esa comunidad lo publicó.
