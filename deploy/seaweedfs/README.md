# Almacén de objetos en desarrollo

`s3.json` son las credenciales de **desarrollo** de SeaweedFS, y están escritas
en claro a propósito: este fichero no vale para producción y no debe copiarse a
un despliegue real.

En producción no se opera un almacén propio. El Cloud usa el almacenamiento de
objetos del proveedor, y las credenciales llegan por variables de entorno
(`STORAGE_ACCESS_KEY`, `STORAGE_SECRET_KEY`). Ver ADR-0016.

Para una instalación autoalojada que sí quiera SeaweedFS: cambia estas claves
antes de exponer nada, y añade `s3.json` a tu propia gestión de secretos.
