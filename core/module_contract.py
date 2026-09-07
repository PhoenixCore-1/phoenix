"""
Phoenix Module Contract v0.3

A module is a package of business capability that plugs into Phoenix Core.
Core owns identity, tenant isolation, permissions, navigation registration,
audit/event services and common workflow infrastructure.

A module owns its own business entities and business rules.
"""

from dataclasses import dataclass, field
from typing import List, Dict


@dataclass(frozen=True)
class ModulePermission:
    code: str
    name: str
    description: str = ""


@dataclass(frozen=True)
class ModuleMenuItem:
    code: str
    label: str
    route: str
    permission: str = ""
    order: int = 100


@dataclass(frozen=True)
class PhoenixModule:
    code: str
    name: str
    version: str
    description: str
    core: bool = False
    permissions: List[ModulePermission] = field(default_factory=list)
    menu: List[ModuleMenuItem] = field(default_factory=list)
    settings_schema: Dict = field(default_factory=dict)


CRM_MODULE = PhoenixModule(
    code="crm", name="CRM", version="0.1", description="Customer relationship management",
    permissions=[ModulePermission("crm.view", "View CRM", "Access CRM records"), ModulePermission("crm.manage", "Manage CRM", "Create and manage CRM records")],
    menu=[ModuleMenuItem("crm.home", "CRM", "/crm", "crm.view", 20)],
    settings_schema={"account_types": ["Customer", "Prospect", "Partner", "Supplier", "Other"]},
)

PROJECTS_MODULE = PhoenixModule(
    code="projects", name="Projects", version="0.1", description="Project management",
    permissions=[ModulePermission("projects.view", "View Projects", "Access project records"), ModulePermission("projects.manage", "Manage Projects", "Create and manage project records")],
    menu=[ModuleMenuItem("projects.home", "Projects", "/projects", "projects.view", 30)],
    settings_schema={"priorities": ["Low", "Normal", "High", "Critical"]},
)

SALES_MODULE = PhoenixModule(
    code="sales", name="Sales", version="0.1", description="Sales and quoting",
    permissions=[ModulePermission("sales.view", "View Sales", "Access sales records"), ModulePermission("sales.manage", "Manage Sales", "Create and manage sales records")],
    menu=[ModuleMenuItem("sales.home", "Sales", "/sales", "sales.view", 40)],
    settings_schema={"currencies": ["ZAR", "USD", "EUR", "GBP"]},
)

PRODUCTION_MODULE = PhoenixModule(
    code="production", name="Production", version="1.0.0", description="Production management",
    permissions=[
        ModulePermission("production.view", "View Production", "Access production records"),
        ModulePermission("production.manage", "Manage Production", "Create and manage production records"),
        ModulePermission("production.operate", "Operate Production", "Start and operate production stages"),
        ModulePermission("production.hold", "Place Production on Hold", "Place production stages on hold"),
        ModulePermission("production.resume", "Resume Production", "Resume production after a hold"),
    ],
    menu=[ModuleMenuItem("production.home", "Production", "/production", "production.view", 50)],
    settings_schema={"stage_templates": ["Production", "Plating", "Assembly", "Packaging"]},
)

ACCOUNT_360_MODULE = PhoenixModule(
    code="account_360",
    name="Account 360",
    version="1.0.0",
    description="Unified customer account financial, commercial and operational experience",
    permissions=[
        ModulePermission("account_360.view", "View Account 360", "Access the unified customer account view"),
        ModulePermission("account_360.financial.view", "View Account 360 Financial", "Access financial information in Account 360"),
        ModulePermission("account_360.commercial.view", "View Account 360 Commercial", "Access commercial information in Account 360"),
        ModulePermission("account_360.operations.view", "View Account 360 Operations", "Access operational information in Account 360"),
        ModulePermission("account_360.communication.view", "View Account 360 Communication", "Access communication and relationship metadata"),
        ModulePermission("account_360.communication.content.view", "View Account 360 Communication Content", "Access protected communication content where authorized"),
        ModulePermission("account_360.timeline.view", "View Account 360 Timeline", "Access the unified account timeline"),
        ModulePermission("account_360.actions.execute", "Execute Account 360 Actions", "Execute authorized actions from Account 360"),
        ModulePermission("account_360.ai.use", "Use Account 360 AI", "Use Account 360 AI capabilities"),
        ModulePermission("account_360.ai.action.execute", "Execute Account 360 AI Actions", "Execute explicitly authorized AI-proposed actions"),
    ],
    menu=[ModuleMenuItem("account_360.home", "Account 360", "/account-360", "account_360.view", 60)],
)


BUILTIN_MODULES = [CRM_MODULE, PROJECTS_MODULE, SALES_MODULE, PRODUCTION_MODULE, ACCOUNT_360_MODULE]


def module_catalog():
    return [
        {
            "code": m.code,
            "name": m.name,
            "version": m.version,
            "description": m.description,
            "core": m.core,
            "permissions": [p.__dict__ for p in m.permissions],
            "menu": [i.__dict__ for i in m.menu],
        }
        for m in BUILTIN_MODULES
    ]
