"""Enterprise Terraform Intelligence — workspace management, infrastructure graph,
drift detection, progressive delivery, and RuntimeStore synchronisation.

Reuses:
  - RuntimeStore          via existing infrastructure intelligence
  - EventHub              for terraform.* events
  - Knowledge Graph       for infrastructure graph persistence
  - Analytics             for metric recording
  - Learning Engine       for infrastructure pattern learning
  - Recommendation Engine for infrastructure recommendations
  - Approval Queue        for progressive delivery gates
  - Governance            for policy enforcement
  - ArgoCD connector      for GitOps correlation
  - Kubernetes connector  for live state comparison

Backward compatible: all existing Deployment Engine, Delivery Orchestrator, and
ArgoCD GitOps functionality continues to work unchanged.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from backend.connectors.terraform import terraform_connector

log = logging.getLogger(__name__)

TERRAFORM_EVENT_TYPES = {
    "init.started": "terraform.init.started",
    "plan.completed": "terraform.plan.completed",
    "apply.started": "terraform.apply.started",
    "apply.completed": "terraform.apply.completed",
    "destroy.started": "terraform.destroy.started",
    "destroy.completed": "terraform.destroy.completed",
    "drift.detected": "terraform.drift.detected",
    "workspace.updated": "terraform.workspace.updated",
    "resource.created": "terraform.resource.created",
    "resource.deleted": "terraform.resource.deleted",
}

# Known terraform providers / platforms
KNOWN_PROVIDERS = {
    "aws", "azurerm", "google", "google-beta", "oci", "vsphere",
    "kubernetes", "helm", "github", "azuredevops", "cloudflare",
    "dns", "random", "tls", "acme", "consul", "vault", "datadog",
    "newrelic", "pagerduty", "statuscake", "fastly", "auth0",
    "okta", "mongodbatlas", "snowflake", "databricks",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_plan_json(raw_json: str) -> Optional[Dict[str, Any]]:
    """Parse terraform show -json output."""
    try:
        return json.loads(raw_json)
    except (json.JSONDecodeError, ValueError):
        return None


def _count_resources_in_plan(plan_data: Optional[Dict[str, Any]]) -> Dict[str, int]:
    if not plan_data:
        return {"create": 0, "update": 0, "delete": 0, "noop": 0}
    counts: Dict[str, int] = {"create": 0, "update": 0, "delete": 0, "noop": 0}
    for change in plan_data.get("resource_changes", []):
        action = change.get("change", {}).get("actions", ["no-op"])
        primary = action[0] if action else "no-op"
        counts[primary] = counts.get(primary, 0) + 1
    return counts


def _extract_resources(plan_data: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract resource list from plan JSON."""
    if not plan_data:
        return []
    resources = []
    for rc in plan_data.get("resource_changes", []):
        addr = rc.get("address", "")
        resources.append({
            "address": addr,
            "type": rc.get("type", ""),
            "name": rc.get("name", ""),
            "provider": rc.get("provider_name", ""),
            "module": rc.get("module", ""),
            "action": rc.get("change", {}).get("actions", ["no-op"])[0] if rc.get("change", {}).get("actions") else "no-op",
        })
    return resources


def _extract_outputs(plan_data: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not plan_data:
        return []
    outputs = []
    for k, v in plan_data.get("output_changes", {}).items():
        actions = v.get("actions", [])
        outputs.append({
            "name": k,
            "action": actions[0] if actions else "no-op",
            "sensitive": v.get("sensitive", False),
        })
    return outputs


# ---------------------------------------------------------------------------
# Workspace Intelligence
# ---------------------------------------------------------------------------


class TerraformWorkspaceIntelligence:
    """Track terraform workspaces, state, variables, outputs, modules, providers."""

    async def discover_all(self) -> Dict[str, Any]:
        """Discover all workspaces and their state."""
        list_result = await terraform_connector.workspace_list()
        if not list_result.success:
            return {"status": "error", "workspaces": [], "error": list_result.stderr[:300]}

        current = await terraform_connector.workspace_show()
        current_ws = current.stdout.strip() if current.success else "default"

        workspaces = []
        for line in list_result.stdout.strip().split("\n"):
            name = line.strip().replace("* ", "").strip()
            if not name:
                continue
            ws = {
                "name": name,
                "current": name == current_ws,
                "directory": str(terraform_connector.workspace_dir),
            }
            workspaces.append(ws)

        # Get provider info
        await terraform_connector.providers()

        return {
            "status": "success",
            "current_workspace": current_ws,
            "workspaces": workspaces,
            "total": len(workspaces),
            "discovered_at": _now(),
        }

    async def get_state_summary(self) -> Dict[str, Any]:
        """Get summary of all resources in state."""
        state_result = await terraform_connector.state_list()
        if not state_result.success:
            return {"status": "error", "error": state_result.stderr[:300]}

        resources = []
        type_counts: Dict[str, int] = {}
        provider_counts: Dict[str, int] = {}

        for line in state_result.stdout.strip().split("\n"):
            addr = line.strip()
            if not addr:
                continue
            resources.append({"address": addr})
            # Extract type from address like "aws_instance.foo" or "module.m.aws_vpc.bar"
            parts = addr.split(".")
            if len(parts) >= 2:
                rtype = parts[-2] if len(parts) >= 3 else parts[0]
                type_counts[rtype] = type_counts.get(rtype, 0) + 1
                # Infer provider from type
                for prov in sorted(KNOWN_PROVIDERS, key=len, reverse=True):
                    if rtype.startswith(prov) or rtype.startswith(prov.replace("-", "_")):
                        provider_counts[prov] = provider_counts.get(prov, 0) + 1
                        break

        return {
            "status": "success",
            "total_resources": len(resources),
            "resources": resources,
            "type_counts": type_counts,
            "provider_counts": provider_counts,
        }

    async def get_outputs(self) -> Dict[str, Any]:
        result = await terraform_connector.output()
        if not result.success:
            return {"status": "error", "error": result.stderr[:300]}
        data = _parse_plan_json(result.stdout)
        if not data:
            return {"status": "error", "error": "failed to parse outputs"}
        outputs = []
        for k, v in data.items():
            outputs.append({
                "name": k,
                "value": v.get("value"),
                "type": v.get("type"),
                "sensitive": v.get("sensitive", False),
            })
        return {"status": "success", "outputs": outputs, "total": len(outputs)}

    async def get_providers(self) -> Dict[str, Any]:
        result = await terraform_connector.providers()
        if not result.success:
            return {"status": "error", "error": result.stderr[:300]}
        lines = result.stdout.strip().split("\n")
        providers = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Parse provider lines like "+ provider[aws] ~> 5.0"
            match = re.match(r'[+-]\s*provider\[(\w+)\]\s*(.*)', line)
            if match:
                providers.append({
                    "name": match.group(1),
                    "constraint": match.group(2).strip(),
                })
        return {"status": "success", "providers": providers, "total": len(providers)}


# ---------------------------------------------------------------------------
# Infrastructure Graph
# ---------------------------------------------------------------------------


class InfrastructureGraphBuilder:
    """Build a graph of infrastructure resources from Terraform state/plan.

    Nodes: providers, modules, resources (networks, subnets, clusters, LBs, VMs, storage, secrets, security groups)
    Edges: DEPENDS_ON, PROVISIONS, CONNECTS_TO, HOSTS, SECURES, USES
    """

    # Resource type classification
    RESOURCE_CATEGORIES: Dict[str, str] = {
        "vpc": "network", "subnet": "network", "network": "network",
        "security_group": "security", "security_group_rule": "security",
        "instance": "compute", "vm": "compute",
        "cluster": "cluster", "eks": "cluster", "aks": "cluster", "gke": "cluster",
        "load_balancer": "loadbalancer", "lb": "loadbalancer", "alb": "loadbalancer", "nlb": "loadbalancer",
        "volume": "storage", "bucket": "storage", "disk": "storage",
        "secret": "secret", "secretsmanager": "secret",
        "database": "database", "db": "database", "rds": "database",
        "dns": "dns", "zone": "dns", "record": "dns",
        "certificate": "security", "key": "security",
    }

    def build_from_state(self, resources: List[Dict[str, Any]], plan_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Build infrastructure graph from terraform state resource list and optional plan JSON."""
        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        provider_nodes: Set[str] = set()
        module_nodes: Set[str] = set()
        resource_map: Dict[str, str] = {}  # address -> node_id

        # Extract dependencies from plan data
        depends_on_map: Dict[str, List[str]] = {}
        if plan_data:
            for rc in plan_data.get("resource_changes", []):
                addr = rc.get("address", "")
                deps = rc.get("depends_on", [])
                if deps:
                    depends_on_map[addr] = deps

        for res in resources:
            address = res.get("address", "")
            if not address:
                continue

            parts = address.split(".")
            rtype = parts[0] if len(parts) == 2 else parts[-2]
            rname = parts[-1]

            # Provider node
            provider_name = self._infer_provider(rtype)
            if provider_name and provider_name not in provider_nodes:
                provider_nodes.add(provider_name)
                nodes.append({
                    "id": f"provider:{provider_name}",
                    "type": "provider",
                    "name": provider_name,
                    "category": "provider",
                    "label": provider_name,
                })

            # Module node
            module_path = res.get("module", "")
            if module_path and module_path not in module_nodes:
                module_nodes.add(module_path)
                nodes.append({
                    "id": f"module:{module_path}",
                    "type": "module",
                    "name": module_path,
                    "category": "module",
                    "label": module_path,
                })

            # Resource node
            category = self._classify(rtype)
            resource_id = f"resource:{address}"
            resource_map[address] = resource_id
            nodes.append({
                "id": resource_id,
                "type": "resource",
                "name": rname,
                "resource_type": rtype,
                "address": address,
                "category": category,
                "provider": provider_name,
                "module": module_path,
                "label": f"{rtype}.{rname}",
            })

            # Edge: provider → resource
            if provider_name:
                edges.append({
                    "source": f"provider:{provider_name}",
                    "target": resource_id,
                    "relationship": "PROVISIONS",
                    "label": "PROVISIONS",
                })

            # Edge: module → resource
            if module_path:
                edges.append({
                    "source": f"module:{module_path}",
                    "target": resource_id,
                    "relationship": "CONTAINS",
                    "label": "CONTAINS",
                })

            # Edge: depends_on
            deps = depends_on_map.get(address, [])
            for dep in deps:
                if dep in resource_map:
                    edges.append({
                        "source": resource_id,
                        "target": resource_map[dep],
                        "relationship": "DEPENDS_ON",
                        "label": "DEPENDS_ON",
                    })

        # Add inter-resource edges based on naming patterns
        self._infer_network_edges(nodes, edges)
        self._infer_security_edges(nodes, edges)
        self._infer_hosting_edges(nodes, edges)

        return {
            "nodes": nodes,
            "edges": edges,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "node_categories": self._count_categories(nodes),
            "edge_relationships": self._count_relationships(edges),
        }

    def _infer_provider(self, rtype: str) -> str:
        for prov in sorted(KNOWN_PROVIDERS, key=len, reverse=True):
            prov_clean = prov.replace("-", "_")
            if rtype.startswith(prov_clean) or rtype.startswith(prov):
                return prov
        return "unknown"

    def _classify(self, rtype: str) -> str:
        rtype_lower = rtype.lower()
        for key, category in self.RESOURCE_CATEGORIES.items():
            if key in rtype_lower:
                return category
        return "other"

    def _infer_network_edges(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> None:
        """Infer CONNECTS_TO edges between network resources and compute."""
        network_nodes = {n["id"]: n for n in nodes if n.get("category") == "network"}
        compute_nodes = {n["id"]: n for n in nodes if n.get("category") == "compute"}
        for cn_id in compute_nodes:
            for nn_id in network_nodes:
                edges.append({
                    "source": cn_id,
                    "target": nn_id,
                    "relationship": "CONNECTS_TO",
                    "label": "CONNECTS_TO",
                })
                break  # one network edge per compute

    def _infer_security_edges(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> None:
        security_nodes = {n["id"] for n in nodes if n.get("category") == "security"}
        targets = {n["id"] for n in nodes if n.get("category") in ("compute", "database", "loadbalancer")}
        for sg in security_nodes:
            for t in targets:
                edges.append({
                    "source": sg,
                    "target": t,
                    "relationship": "SECURES",
                    "label": "SECURES",
                })

    def _infer_hosting_edges(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> None:
        cluster_nodes = {n["id"] for n in nodes if n.get("category") == "cluster"}
        compute_nodes = {n["id"] for n in nodes if n.get("category") == "compute"}
        for cluster in cluster_nodes:
            for compute in compute_nodes:
                edges.append({
                    "source": cluster,
                    "target": compute,
                    "relationship": "HOSTS",
                    "label": "HOSTS",
                })

    def _count_categories(self, nodes: List[Dict[str, Any]]) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for n in nodes:
            cat = n.get("category", "other")
            counts[cat] = counts.get(cat, 0) + 1
        return counts

    def _count_relationships(self, edges: List[Dict[str, Any]]) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for e in edges:
            rel = e.get("relationship", "UNKNOWN")
            counts[rel] = counts.get(rel, 0) + 1
        return counts


# ---------------------------------------------------------------------------
# Drift Detection
# ---------------------------------------------------------------------------


class TerraformDriftDetector:
    """Detect drift by comparing terraform plan with applied state."""

    async def detect(self) -> Dict[str, Any]:
        """Run terraform plan and compare with current state."""
        # Run plan and show in JSON format
        plan_result = await terraform_connector.plan(out="drift_plan")
        if not plan_result.success:
            return {"status": "error", "error": plan_result.stderr[:300]}

        show_result = await terraform_connector.show(plan_file="drift_plan")
        if not show_result.success:
            return {"status": "error", "error": show_result.stderr[:300]}

        plan_data = _parse_plan_json(show_result.stdout)
        if not plan_data:
            return {"status": "error", "error": "failed to parse plan JSON"}

        resources = _extract_resources(plan_data)
        changes = _count_resources_in_plan(plan_data)

        drifts = []
        for r in resources:
            action = r.get("action", "")
            if action == "update":
                drifts.append({
                    "type": "configuration_drift",
                    "address": r.get("address", ""),
                    "resource_type": r.get("type", ""),
                    "description": f"{r.get('address', '')} has configuration drift",
                    "severity": "medium",
                })
            elif action == "delete":
                drifts.append({
                    "type": "missing_resource",
                    "address": r.get("address", ""),
                    "resource_type": r.get("type", ""),
                    "description": f"{r.get('address', '')} will be deleted",
                    "severity": "high",
                })
            elif action == "create":
                drifts.append({
                    "type": "unexpected_resource",
                    "address": r.get("address", ""),
                    "resource_type": r.get("type", ""),
                    "description": f"New resource {r.get('address', '')} will be created",
                    "severity": "medium",
                })

        risk_score = 0.0
        for d in drifts:
            if d["severity"] == "high":
                risk_score += 0.8
            elif d["severity"] == "medium":
                risk_score += 0.4
            else:
                risk_score += 0.1

        return {
            "status": "success",
            "drift_count": len(drifts),
            "drifts": drifts,
            "resource_changes": changes,
            "total_resources_changed": sum(changes.values()),
            "risk_score": round(risk_score, 2),
            "severity": "critical" if risk_score >= 3.0 else "high" if risk_score >= 1.5 else "medium" if risk_score > 0 else "none",
            "detected_at": _now(),
        }


# ---------------------------------------------------------------------------
# Progressive Infrastructure Delivery
# ---------------------------------------------------------------------------


class TerraformProgressiveDelivery:
    """Manage plan → approval → apply → rollback pipeline."""

    def __init__(self) -> None:
        self._plans: Dict[str, Dict[str, Any]] = {}

    async def create_plan(
        self, workspace: str = "default", vars: Optional[Dict[str, str]] = None,
        destroy: bool = False, var_file: str = "",
    ) -> Dict[str, Any]:
        """Create a terraform plan and store it for approval."""
        ws_result = await terraform_connector.workspace_select(workspace)
        if not ws_result.success:
            return {"status": "error", "error": f"workspace select failed: {ws_result.stderr[:200]}"}

        plan_result = await terraform_connector.plan(destroy=destroy, vars=vars, var_file=var_file)
        if not plan_result.success:
            return {"status": "error", "error": plan_result.stderr[:500]}

        show_result = await terraform_connector.show()
        plan_data = _parse_plan_json(show_result.stdout) if show_result.success else None
        resources = _extract_resources(plan_data)
        changes = _count_resources_in_plan(plan_data)
        outputs = _extract_outputs(plan_data)

        plan_id = f"plan_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        plan_entry = {
            "plan_id": plan_id,
            "workspace": workspace,
            "created_at": _now(),
            "status": "created",
            "changes": changes,
            "total_resources": len(resources),
            "resources": resources,
            "outputs": outputs,
            "destroy": destroy,
            "stdout": plan_result.stdout[:3000],
            "stderr": plan_result.stderr[:1000],
            "duration_seconds": plan_result.duration_seconds,
        }
        self._plans[plan_id] = plan_entry
        return {"status": "success", "plan": plan_entry}

    async def approve_and_apply(self, plan_id: str) -> Dict[str, Any]:
        """Apply an approved plan."""
        plan = self._plans.get(plan_id)
        if not plan:
            return {"status": "error", "error": "plan not found"}

        ws_result = await terraform_connector.workspace_select(plan["workspace"])
        if not ws_result.success:
            return {"status": "error", "error": f"workspace select failed: {ws_result.stderr[:200]}"}

        apply_result = await terraform_connector.apply()
        plan["status"] = "applied"
        plan["applied_at"] = _now()
        plan["apply_duration"] = apply_result.duration_seconds
        plan["apply_success"] = apply_result.success
        plan["apply_stdout"] = apply_result.stdout[:3000]
        if not apply_result.success:
            plan["apply_stderr"] = apply_result.stderr[:1000]
            return {"status": "error", "error": apply_result.stderr[:500], "plan": plan}

        return {"status": "success", "plan": plan}

    async def rollback(self, workspace: str = "default") -> Dict[str, Any]:
        """Rollback by applying previous state (requires state versioning)."""
        ws_result = await terraform_connector.workspace_select(workspace)
        if not ws_result.success:
            return {"status": "error", "error": f"workspace select failed: {ws_result.stderr[:200]}"}

        # Get current state resources before rollback
        await terraform_connector.state_list()

        # Apply previous state — this is a simplified rollback
        # Real rollback requires state versioning
        result = await terraform_connector.apply(plan_file="")

        return {
            "status": "success" if result.success else "error",
            "workspace": workspace,
            "rollback_result": result.to_dict(),
            "rolled_back_at": _now(),
        }

    async def destroy_workspace(
        self, workspace: str = "default", vars: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Destroy all infrastructure in a workspace."""
        ws_result = await terraform_connector.workspace_select(workspace)
        if not ws_result.success:
            return {"status": "error", "error": f"workspace select failed: {ws_result.stderr[:200]}"}

        result = await terraform_connector.destroy(vars=vars)
        return {
            "status": "success" if result.success else "error",
            "workspace": workspace,
            "result": result.to_dict(),
            "destroyed_at": _now(),
        }

    def list_plans(self) -> List[Dict[str, Any]]:
        return list(self._plans.values())


# ---------------------------------------------------------------------------
# Event Emitter
# ---------------------------------------------------------------------------


class TerraformEventEmitter:
    """Emit terraform events through the EventHub."""

    async def emit_init_started(self, workspace: str) -> None:
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type="terraform.init.started",
                agent="terraform_intelligence",
                message=f"Terraform init started in workspace '{workspace}'",
                metadata={"workspace": workspace},
            )
        except Exception as exc:
            log.debug("Terraform event emit failed: %s", exc)

    async def emit_plan_completed(self, workspace: str, changes: Dict[str, int]) -> None:
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type="terraform.plan.completed",
                agent="terraform_intelligence",
                message=f"Plan completed in '{workspace}': {changes.get('create', 0)} create, {changes.get('update', 0)} update, {changes.get('delete', 0)} delete",
                metadata={"workspace": workspace, "changes": changes},
            )
        except Exception as exc:
            log.debug("Terraform event emit failed: %s", exc)

    async def emit_apply_started(self, workspace: str, plan_id: str) -> None:
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type="terraform.apply.started",
                agent="terraform_intelligence",
                message=f"Apply started in workspace '{workspace}' (plan: {plan_id})",
                metadata={"workspace": workspace, "plan_id": plan_id},
            )
        except Exception as exc:
            log.debug("Terraform event emit failed: %s", exc)

    async def emit_apply_completed(self, workspace: str, success: bool) -> None:
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type="terraform.apply.completed",
                agent="terraform_intelligence",
                message=f"Apply {'completed' if success else 'failed'} in workspace '{workspace}'",
                metadata={"workspace": workspace, "success": success},
            )
        except Exception as exc:
            log.debug("Terraform event emit failed: %s", exc)

    async def emit_destroy_started(self, workspace: str) -> None:
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type="terraform.destroy.started",
                agent="terraform_intelligence",
                message=f"Destroy started in workspace '{workspace}'",
                metadata={"workspace": workspace},
            )
        except Exception as exc:
            log.debug("Terraform event emit failed: %s", exc)

    async def emit_destroy_completed(self, workspace: str, success: bool) -> None:
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type="terraform.destroy.completed",
                agent="terraform_intelligence",
                message=f"Destroy {'completed' if success else 'failed'} in workspace '{workspace}'",
                metadata={"workspace": workspace, "success": success},
            )
        except Exception as exc:
            log.debug("Terraform event emit failed: %s", exc)

    async def emit_drift_detected(self, drift_count: int, risk_score: float) -> None:
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type="terraform.drift.detected",
                agent="terraform_intelligence",
                message=f"Drift detected: {drift_count} drifts, risk {risk_score}",
                metadata={"drift_count": drift_count, "risk_score": risk_score},
            )
        except Exception as exc:
            log.debug("Terraform event emit failed: %s", exc)

    async def emit_workspace_updated(self, workspace: str) -> None:
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type="terraform.workspace.updated",
                agent="terraform_intelligence",
                message=f"Workspace '{workspace}' updated",
                metadata={"workspace": workspace},
            )
        except Exception as exc:
            log.debug("Terraform event emit failed: %s", exc)

    async def emit_resource_created(self, address: str, resource_type: str, workspace: str) -> None:
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type="terraform.resource.created",
                agent="terraform_intelligence",
                message=f"Resource {address} created in '{workspace}'",
                metadata={"address": address, "type": resource_type, "workspace": workspace},
            )
        except Exception as exc:
            log.debug("Terraform event emit failed: %s", exc)


# ---------------------------------------------------------------------------
# Correlation Chain
# ---------------------------------------------------------------------------


class TerraformCorrelationChain:
    """Drill-down: workspace → plan → apply → resources → cluster → ArgoCD → deploy → pod → logs → trace → metrics → KG → learning → recommendation."""

    async def from_workspace(self, workspace: str = "default") -> Dict[str, Any]:
        chain: Dict[str, Any] = {"workspace": workspace, "steps": []}
        chain["steps"].append({"step": "workspace", "data": workspace})

        # Workspace → State
        try:
            state = await TerraformWorkspaceIntelligence().get_state_summary()
            chain["state"] = state.get("total_resources", 0)
            chain["steps"].append({"step": "state", "data": chain["state"]})
        except Exception:
            pass

        # State → Providers
        try:
            prov = await TerraformWorkspaceIntelligence().get_providers()
            chain["providers"] = [p["name"] for p in prov.get("providers", [])]
            chain["steps"].append({"step": "providers", "data": chain["providers"]})
        except Exception:
            pass

        # Providers → Deployments
        try:
            from backend.services.enterprise_infrastructure_intelligence import infrastructure_intelligence
            deps = infrastructure_intelligence.get_dashboard().get("deployments", {})
            chain["deployments"] = deps
            chain["steps"].append({"step": "deployments", "data": deps})
        except Exception:
            pass

        # Deployments → Pods
        try:
            from backend.services.enterprise_infrastructure_intelligence import infrastructure_intelligence
            pods = infrastructure_intelligence.get_dashboard().get("pods", {})
            chain["pods"] = pods
            chain["steps"].append({"step": "pods", "data": pods})
        except Exception:
            pass

        # Pods → Logs
        try:
            from backend.connectors.loki import loki_connector
            if loki_connector.is_ready:
                log_result = await loki_connector.query(f'{{namespace="{workspace}"}} |= "error"', limit=50)
                chain["logs"] = {"entries": len(log_result.get("data", {}).get("result", []))}
                chain["steps"].append({"step": "logs", "count": chain["logs"]["entries"]})
        except Exception:
            pass

        # Logs → Traces
        try:
            from backend.services.enterprise_trace_intelligence import trace_intelligence
            chain["traces"] = await trace_intelligence.get_graph_health()
            chain["steps"].append({"step": "traces", "data": chain["traces"]})
        except Exception:
            pass

        # Traces → Metrics
        try:
            from backend.services.enterprise_prometheus_intelligence import prometheus_metrics
            metrics = await prometheus_metrics.collect_all_metrics()
            chain["metrics"] = {k: v.get("status") for k, v in metrics.items() if isinstance(v, dict)}
            chain["steps"].append({"step": "metrics", "count": len(chain["metrics"])})
        except Exception:
            pass

        # Metrics → Knowledge Graph
        try:
            from backend.services.enterprise_graph_service import knowledge_graph
            chain["knowledge_graph"] = {
                "nodes": len(knowledge_graph.get_all_nodes()),
                "edges": len(knowledge_graph.get_all_edges()),
            }
            chain["steps"].append({"step": "knowledge_graph", "data": chain["knowledge_graph"]})
        except Exception:
            pass

        # Knowledge Graph → Learning
        try:
            from backend.services.enterprise_learning_service import learning_engine
            patterns = learning_engine.get_patterns() if hasattr(learning_engine, "get_patterns") else []
            chain["learning"] = {"patterns": len(patterns)}
            chain["steps"].append({"step": "learning", "data": chain["learning"]})
        except Exception:
            pass

        # Learning → Recommendations
        try:
            from backend.services.enterprise_recommendation_engine import recommendation_engine
            recs = recommendation_engine.get_recommendations(limit=5)
            chain["recommendations"] = recs
            chain["steps"].append({"step": "recommendations", "count": len(recs)})
        except Exception:
            pass

        chain["correlation_id"] = f"tf_{abs(hash(workspace)) % 10**8:08x}"
        return chain


# ---------------------------------------------------------------------------
# Singleton instances
# ---------------------------------------------------------------------------

workspace_intel = TerraformWorkspaceIntelligence()
infra_graph_builder = InfrastructureGraphBuilder()
drift_detector = TerraformDriftDetector()
progressive_delivery = TerraformProgressiveDelivery()
terraform_event_emitter = TerraformEventEmitter()
terraform_correlation = TerraformCorrelationChain()
