from app.modules.account.plugin import AccountPlugin
from app.modules.admin.plugin import AdminPlugin
from app.modules.auth.plugin import AuthPlugin
from app.modules.dashboard.plugin import DashboardPlugin
from app.modules.databases.plugin import DatabasesPlugin
from app.modules.dns.plugin import DnsPlugin
from app.modules.domains.plugin import DomainsPlugin
from app.modules.importers.plugin import ImportersPlugin
from app.modules.mail.plugin import MailPlugin
from app.modules.maintenance.plugin import MaintenancePlugin
from app.modules.oidc.plugin import OIDCPlugin
from app.modules.plans.plugin import PlansPlugin
from app.modules.projects.plugin import ProjectsPlugin
from app.modules.public.plugin import PublicPlugin
from app.modules.servers.plugin import ServersPlugin
from app.modules.workspaces.plugin import WorkspacesPlugin
from app.plugins import registry


def load_plugins() -> None:
    registry.clear()
    registry.add(PublicPlugin())
    registry.add(AuthPlugin())
    registry.add(DashboardPlugin())
    registry.add(ProjectsPlugin())
    registry.add(DatabasesPlugin())
    registry.add(ServersPlugin())
    registry.add(MailPlugin())
    registry.add(OIDCPlugin())
    registry.add(DnsPlugin())
    registry.add(DomainsPlugin())
    registry.add(MaintenancePlugin())
    registry.add(PlansPlugin())
    registry.add(AccountPlugin())
    registry.add(AdminPlugin())
    registry.add(ImportersPlugin())
    registry.add(WorkspacesPlugin())
