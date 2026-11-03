from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any

from visionqc.application.services import (FactoryMemoryService, InspectionApplicationService,
    VoiceAssistantService, RootCauseIntelligenceService, PredictiveQualityService, AIFactoryEngineerService, ReleaseReadinessService, EnterpriseIntegrationService, IndustrialAutomationService, CommercialEditionService, FactoryLearningService)
from visionqc.application.services.knowledge_graph_service import KnowledgeGraphService
from visionqc.core.database import initialize_database
from visionqc.core.migrations import apply_pending_migrations
from visionqc.core.settings import app_data_dir
from visionqc.infrastructure.config import JsonSettingsProvider
from visionqc.infrastructure.persistence import SqliteFactoryMemoryRepository, SqliteInspectionRepository, SqliteVoiceConversationRepository, SqliteAuditTrailRepository, SqliteApiKeyRepository, SqliteIndustrialAutomationRepository, SqliteCommercialRepository
from visionqc.infrastructure.persistence.sqlite_knowledge_graph import SqliteKnowledgeGraphRepository
from visionqc.platform import InProcessEventBus, ServiceContainer
from visionqc.platform.logging import configure_logging
from visionqc.plugins import PluginManager
from visionqc.security import SecurityRepository, SecurityGovernanceService
from visionqc.integration import ConnectorRegistry, RestApiConnector, MqttConnector, OpcUaConnector, WebhookConnector, FileExchangeConnector, VisionQCRestServer

logger = logging.getLogger(__name__)

@dataclass(slots=True)
class ApplicationContext:
    container: ServiceContainer
    settings: dict[str, Any]
    log_path: Path
    plugin_manager: PluginManager


def bootstrap_application() -> ApplicationContext:
    settings_provider=JsonSettingsProvider(); settings=settings_provider.load()
    log_path=configure_logging(app_data_dir()/"logs"); initialize_database(); apply_pending_migrations()
    container=ServiceContainer(); event_bus=InProcessEventBus()
    inspection_repository=SqliteInspectionRepository(); inspection_service=InspectionApplicationService(inspection_repository,event_bus)
    factory_memory_repository=SqliteFactoryMemoryRepository(); factory_memory_service=FactoryMemoryService(factory_memory_repository,event_bus)
    factory_learning_service=FactoryLearningService(factory_memory_service)
    voice_repository=SqliteVoiceConversationRepository()
    knowledge_graph_repository=SqliteKnowledgeGraphRepository(); knowledge_graph_service=KnowledgeGraphService(knowledge_graph_repository,factory_memory_service,event_bus)
    root_cause_service=RootCauseIntelligenceService(factory_memory_service,event_bus,knowledge_graph=knowledge_graph_service)
    predictive_quality_service=PredictiveQualityService(factory_memory_service,event_bus,knowledge_graph=knowledge_graph_service)
    factory_engineer_service=AIFactoryEngineerService(factory_memory_service,predictive_quality_service,root_cause_service,knowledge_graph_service,event_bus)
    audit_repository=SqliteAuditTrailRepository(); audit_repository.initialize()
    security_repository=SecurityRepository(); security_service=SecurityGovernanceService(security_repository,audit_repository)
    release_readiness_service=ReleaseReadinessService(audit_repository,event_bus)
    api_key_repository=SqliteApiKeyRepository(); api_key_repository.initialize()
    connector_registry=ConnectorRegistry()
    enterprise_integration_service=EnterpriseIntegrationService(connector_registry,api_key_repository,audit_repository,event_bus,factory_memory_service)
    automation_repository=SqliteIndustrialAutomationRepository(); automation_repository.initialize()
    industrial_automation_service=IndustrialAutomationService(automation_repository,audit_repository,event_bus,enterprise_integration_service)
    commercial_repository=SqliteCommercialRepository(); commercial_repository.initialize()
    commercial_edition_service=CommercialEditionService(commercial_repository,audit_repository,event_bus)
    integration_settings=settings.get("enterprise_integration", {}) if isinstance(settings, dict) else {}
    rest_server=VisionQCRestServer(enterprise_integration_service,api_key_repository,port=int(integration_settings.get("rest_port",8765)))
    connector_registry.register(RestApiConnector(rest_server))
    connector_registry.register(MqttConnector(integration_settings.get("mqtt",{})))
    connector_registry.register(OpcUaConnector(integration_settings.get("opcua",{})))
    connector_registry.register(WebhookConnector(integration_settings.get("webhook",{})))
    connector_registry.register(FileExchangeConnector(app_data_dir()/"integration_exchange"))
    voice_assistant_service=VoiceAssistantService(factory_memory_service,voice_repository,event_bus,root_cause_service=root_cause_service,predictive_quality_service=predictive_quality_service,factory_engineer_service=factory_engineer_service)
    for name,value in {"settings_provider":settings_provider,"settings":settings,"event_bus":event_bus,
        "inspection_repository":inspection_repository,"inspection_service":inspection_service,
        "factory_memory_repository":factory_memory_repository,"factory_memory_service":factory_memory_service,"factory_learning_service":factory_learning_service,
        "voice_repository":voice_repository,"knowledge_graph_repository":knowledge_graph_repository,
        "knowledge_graph_service":knowledge_graph_service,"root_cause_service":root_cause_service,
        "predictive_quality_service":predictive_quality_service,"factory_engineer_service":factory_engineer_service,"voice_assistant_service":voice_assistant_service,
        "audit_repository":audit_repository,"security_repository":security_repository,"security_service":security_service,"release_readiness_service":release_readiness_service,
        "api_key_repository":api_key_repository,"connector_registry":connector_registry,"enterprise_integration_service":enterprise_integration_service,"automation_repository":automation_repository,"industrial_automation_service":industrial_automation_service,"commercial_repository":commercial_repository,"commercial_edition_service":commercial_edition_service,"rest_server":rest_server}.items():
        container.register_instance(name,value)
    plugin_manager=PluginManager(container,app_data_dir()/"plugins"); plugin_manager.load_all(); container.register_instance("plugin_manager",plugin_manager)
    logger.info("VisionQC application context initialized")
    return ApplicationContext(container=container,settings=settings,log_path=log_path,plugin_manager=plugin_manager)
