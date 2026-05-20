"""Import target modules (each calls register_import_target on load)."""
from app.data_imports.targets import aircraft as _aircraft  # noqa: F401
from app.data_imports.targets import atl as _atl  # noqa: F401
from app.data_imports.targets import maintenance_ad as _maintenance_ad  # noqa: F401
from app.data_imports.targets import maintenance_ad_work_orders as _maintenance_ad_work_orders  # noqa: F401
from app.data_imports.targets import maintenance_cpcp as _maintenance_cpcp  # noqa: F401
from app.data_imports.targets import maintenance_ldnd as _maintenance_ldnd  # noqa: F401
from app.data_imports.targets import maintenance_tcc as _maintenance_tcc  # noqa: F401
