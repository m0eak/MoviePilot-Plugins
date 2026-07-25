import copy
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.db.site_oper import SiteOper
from app.db.systemconfig_oper import SystemConfigOper
from app.helper.sites import SitesHelper  # noqa
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import SystemConfigKey
from app.utils.string import StringUtils


class PublicBtIndexer(_PluginBase):
    """
    公开 BT 索引站点插件。

    首期仅内置 Nyaa.si：启用后自动注册索引器、创建站点记录，
    并可按配置加入 MoviePilot 原生搜索站点列表，无需 Jackett。
    """

    # 插件名称
    plugin_name = "公开BT索引器"
    # 插件描述
    plugin_desc = "自动注册公开 BT 站点到 MoviePilot 原生搜索，首期支持 Nyaa.si，无需 Jackett。"
    # 插件图标
    plugin_icon = "spider.png"
    # 插件版本
    plugin_version = "1.0.0"
    # 插件作者
    plugin_author = "m0eak"
    # 作者主页
    author_url = "https://github.com/m0eak"
    # 插件配置项ID前缀
    plugin_config_prefix = "publicbtindexer_"
    # 加载顺序
    plugin_order = 28
    # 可使用的用户级别
    auth_level = 1

    # 当前内置站点标识
    _SITE_KEY = "nyaa"
    _SITE_NAME = "Nyaa"
    _SITE_URL = "https://nyaa.si/"
    _SITE_DOMAIN_KEY = "nyaa.si"
    _MANAGED_SITES_DATA_KEY = "managed_sites"

    # 配置
    _enabled: bool = False
    _use_proxy: bool = True
    _timeout: int = 30
    _auto_add_search: bool = True
    _remove_from_search_on_disable: bool = True
    _delete_site_on_disable: bool = False
    _last_status: str = ""

    def init_plugin(self, config: dict = None):
        """
        生效插件配置：启用时注册 Nyaa，禁用时按策略安全回滚。
        """
        config = config or {}
        self._enabled = bool(config.get("enabled"))
        self._use_proxy = bool(config.get("use_proxy", True))
        self._timeout = self._normalize_timeout(config.get("timeout"))
        self._auto_add_search = bool(config.get("auto_add_search", True))
        self._remove_from_search_on_disable = bool(
            config.get("remove_from_search_on_disable", True)
        )
        self._delete_site_on_disable = bool(config.get("delete_site_on_disable", False))
        self._last_status = config.get("last_status") or ""

        if self._enabled:
            ok, message = self._enable_nyaa()
            self._last_status = message
            if ok:
                logger.info(f"[PublicBtIndexer] {message}")
            else:
                logger.error(f"[PublicBtIndexer] {message}")
                self.systemmessage.put(message, title=self.plugin_name)
        else:
            ok, message = self._disable_nyaa()
            self._last_status = message
            if message:
                logger.info(f"[PublicBtIndexer] {message}")

        self.__update_config()

    def get_state(self) -> bool:
        """返回插件启用状态。"""
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        """本插件不注册远程命令。"""
        return []

    def get_api(self) -> List[Dict[str, Any]]:
        """本插件不暴露额外 API。"""
        return []

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        拼装插件配置页面。
        """
        return [
            {
                "component": "VForm",
                "content": [
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "enabled",
                                            "label": "启用插件",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "use_proxy",
                                            "label": "使用系统代理",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "timeout",
                                            "label": "超时秒数",
                                            "type": "number",
                                            "min": 5,
                                            "max": 120,
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "auto_add_search",
                                            "label": "自动加入搜索站点",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "remove_from_search_on_disable",
                                            "label": "禁用时移出搜索列表",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "delete_site_on_disable",
                                            "label": "禁用时删除站点记录",
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [
                                    {
                                        "component": "VAlert",
                                        "props": {
                                            "type": "info",
                                            "variant": "tonal",
                                            "text": (
                                                "启用后会自动注册 Nyaa.si 索引器并创建公开站点记录，"
                                                "默认加入原生搜索站点列表，无需 Jackett。"
                                                "禁用时默认只移出搜索列表，不删除站点；"
                                                "如需删除本插件创建的站点，请显式打开“禁用时删除站点记录”。"
                                            ),
                                        },
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [
                                    {
                                        "component": "VAlert",
                                        "props": {
                                            "type": "warning",
                                            "variant": "tonal",
                                            "text": (
                                                "当前仅支持 Nyaa.si。"
                                                "站点资源依赖 MoviePilot-Resources（SitesHelper）；"
                                                "若主机未安装资源包，启用会失败并给出明确提示。"
                                            ),
                                        },
                                    }
                                ],
                            }
                        ],
                    },
                ],
            }
        ], {
            "enabled": False,
            "use_proxy": True,
            "timeout": 30,
            "auto_add_search": True,
            "remove_from_search_on_disable": True,
            "delete_site_on_disable": False,
            "last_status": "",
        }

    def get_page(self) -> List[dict]:
        """
        展示当前管理状态。
        """
        managed = self._get_managed_sites()
        site_id = managed.get(self._SITE_KEY)
        site = SiteOper().get(site_id) if site_id else SiteOper().get_by_domain(self._SITE_DOMAIN_KEY)
        indexer_sites = SystemConfigOper().get(SystemConfigKey.IndexerSites) or []
        in_search = bool(site and site.id in indexer_sites)

        status_text = self._last_status or "尚未执行注册"
        site_text = (
            f"ID={site.id} / {site.name} / {site.url} / active={site.is_active}"
            if site
            else "尚未创建"
        )
        search_text = "是" if in_search else "否"

        return [
            {
                "component": "VCard",
                "props": {"variant": "outlined", "class": "mb-3"},
                "content": [
                    {
                        "component": "VCardTitle",
                        "text": "公开 BT 索引器状态",
                    },
                    {
                        "component": "VCardText",
                        "content": [
                            {
                                "component": "div",
                                "text": f"插件状态：{'启用' if self._enabled else '禁用'}",
                            },
                            {
                                "component": "div",
                                "text": f"内置站点：{self._SITE_NAME} ({self._SITE_URL})",
                            },
                            {
                                "component": "div",
                                "text": f"站点记录：{site_text}",
                            },
                            {
                                "component": "div",
                                "text": f"是否在搜索站点列表：{search_text}",
                            },
                            {
                                "component": "div",
                                "text": f"最近执行结果：{status_text}",
                            },
                        ],
                    },
                ],
            }
        ]

    def stop_service(self):
        """
        停止插件服务。
        本插件无后台任务，停用时按配置做安全回滚。
        """
        if not self._enabled:
            ok, message = self._disable_nyaa()
            if message:
                self._last_status = message
                self.__update_config()
                logger.info(f"[PublicBtIndexer] stop_service: {message}")

    def __update_config(self):
        """持久化插件配置。"""
        self.update_config(
            {
                "enabled": self._enabled,
                "use_proxy": self._use_proxy,
                "timeout": self._timeout,
                "auto_add_search": self._auto_add_search,
                "remove_from_search_on_disable": self._remove_from_search_on_disable,
                "delete_site_on_disable": self._delete_site_on_disable,
                "last_status": self._last_status,
            }
        )

    def _enable_nyaa(self) -> Tuple[bool, str]:
        """
        启用 Nyaa：注册索引器、确保站点记录、可选加入搜索列表。
        """
        try:
            indexer = self._load_nyaa_profile()
        except Exception as err:
            return False, f"加载 Nyaa 配置失败：{err}"

        indexer = self._apply_runtime_overrides(indexer)

        try:
            sites_helper = SitesHelper()
        except Exception as err:
            return False, (
                "无法初始化 SitesHelper，请确认已安装 MoviePilot-Resources 资源包"
                f"（app/helper/sites.*）：{err}"
            )

        domain_key = StringUtils.get_url_domain(indexer.get("domain") or self._SITE_URL)
        if not domain_key:
            domain_key = self._SITE_DOMAIN_KEY

        try:
            sites_helper.add_indexer(domain_key, indexer)
        except Exception as err:
            return False, f"注册 Nyaa 索引器失败：{err}"

        site, created = self._ensure_site_record(indexer=indexer, domain_key=domain_key)
        if not site:
            return False, "注册索引器成功，但创建/更新站点记录失败"

        managed = self._get_managed_sites()
        managed[self._SITE_KEY] = site.id
        self._save_managed_sites(managed)

        search_msg = ""
        if self._auto_add_search:
            added = self._add_site_to_indexer_sites(site.id)
            search_msg = "，已加入搜索站点列表" if added else "，搜索站点列表已包含该站点"

        action = "创建" if created else "更新"
        return True, (
            f"Nyaa 已就绪：索引器已注册，站点记录已{action}"
            f"（ID={site.id}）{search_msg}"
        )

    def _disable_nyaa(self) -> Tuple[bool, str]:
        """
        禁用 Nyaa：默认移出搜索列表，可选删除本插件管理的站点记录。
        """
        managed = self._get_managed_sites()
        site_id = managed.get(self._SITE_KEY)
        site = None
        if site_id:
            site = SiteOper().get(site_id)
        if not site:
            site = SiteOper().get_by_domain(self._SITE_DOMAIN_KEY)

        actions: List[str] = []
        if site and self._remove_from_search_on_disable:
            removed = self._remove_site_from_indexer_sites(site.id)
            if removed:
                actions.append("已从搜索站点列表移除")

        if site and self._delete_site_on_disable:
            # 仅删除本插件记录过的站点，避免误删用户手工站点
            if managed.get(self._SITE_KEY) == site.id:
                try:
                    SiteOper().delete(site.id)
                    actions.append(f"已删除站点记录 ID={site.id}")
                    managed.pop(self._SITE_KEY, None)
                    self._save_managed_sites(managed)
                except Exception as err:
                    return False, f"删除 Nyaa 站点记录失败：{err}"
            else:
                actions.append("站点非本插件托管，跳过删除")
        elif site and not self._delete_site_on_disable:
            actions.append("保留站点记录")

        if not actions:
            return True, "插件已禁用，无需回滚"

        return True, "插件已禁用：" + "，".join(actions)

    def _load_nyaa_profile(self) -> dict:
        """从插件目录加载 Nyaa 索引配置。"""
        profile_path = Path(__file__).resolve().parent / "profiles" / "nyaa.json"
        if not profile_path.exists():
            raise FileNotFoundError(f"未找到配置文件：{profile_path}")
        with profile_path.open("r", encoding="utf-8") as fp:
            data = json.load(fp)
        if not isinstance(data, dict):
            raise ValueError("Nyaa 配置必须是 JSON 对象")
        if not data.get("domain") or not data.get("search") or not data.get("torrents"):
            raise ValueError("Nyaa 配置缺少 domain/search/torrents 必要字段")
        return data

    def _apply_runtime_overrides(self, indexer: dict) -> dict:
        """按插件配置覆盖代理与超时。"""
        data = copy.deepcopy(indexer)
        data["proxy"] = bool(self._use_proxy)
        data["timeout"] = int(self._timeout)
        data["public"] = True
        data["name"] = data.get("name") or self._SITE_NAME
        data["domain"] = data.get("domain") or self._SITE_URL
        if not str(data["domain"]).endswith("/"):
            data["domain"] = str(data["domain"]) + "/"
        return data

    def _ensure_site_record(self, indexer: dict, domain_key: str) -> Tuple[Optional[Any], bool]:
        """
        确保站点表中存在 Nyaa 记录。
        :return: (site, created)
        """
        site_oper = SiteOper()
        site = site_oper.get_by_domain(domain_key)
        site_url = indexer.get("domain") or self._SITE_URL
        scheme, netloc = StringUtils.get_url_netloc(site_url)
        if scheme and netloc:
            site_url = f"{scheme}://{netloc}/"
        elif not str(site_url).endswith("/"):
            site_url = f"{site_url}/"

        payload = {
            "name": indexer.get("name") or self._SITE_NAME,
            "url": site_url,
            "domain": domain_key,
            "proxy": 1 if self._use_proxy else 0,
            "public": 1,
            "timeout": int(self._timeout),
            "is_active": True,
            "render": 0,
        }

        if site:
            try:
                site_oper.update(
                    site.id,
                    {
                        "name": payload["name"],
                        "url": payload["url"],
                        "proxy": payload["proxy"],
                        "public": payload["public"],
                        "timeout": payload["timeout"],
                        "is_active": True,
                    },
                )
                site = site_oper.get(site.id)
                return site, False
            except Exception as err:
                logger.error(f"[PublicBtIndexer] 更新站点失败：{err}")
                return None, False

        ok, msg = site_oper.add(**payload)
        if not ok:
            # 并发场景下可能已存在
            site = site_oper.get_by_domain(domain_key)
            if site:
                return site, False
            logger.error(f"[PublicBtIndexer] 新增站点失败：{msg}")
            return None, False

        site = site_oper.get_by_domain(domain_key)
        return site, True

    @staticmethod
    def _add_site_to_indexer_sites(site_id: int) -> bool:
        """将站点 ID 加入搜索站点列表，返回是否发生写入。"""
        config = SystemConfigOper()
        selected = list(config.get(SystemConfigKey.IndexerSites) or [])
        if site_id in selected:
            return False
        selected.append(site_id)
        config.set(SystemConfigKey.IndexerSites, selected)
        return True

    @staticmethod
    def _remove_site_from_indexer_sites(site_id: int) -> bool:
        """从搜索站点列表移除站点 ID，返回是否发生写入。"""
        config = SystemConfigOper()
        selected = list(config.get(SystemConfigKey.IndexerSites) or [])
        if site_id not in selected:
            return False
        selected = [item for item in selected if item != site_id]
        config.set(SystemConfigKey.IndexerSites, selected)
        return True

    def _get_managed_sites(self) -> Dict[str, int]:
        """读取本插件托管的站点 ID 映射。"""
        data = self.get_data(self._MANAGED_SITES_DATA_KEY) or {}
        if not isinstance(data, dict):
            return {}
        result: Dict[str, int] = {}
        for key, value in data.items():
            try:
                result[str(key)] = int(value)
            except (TypeError, ValueError):
                continue
        return result

    def _save_managed_sites(self, managed: Dict[str, int]):
        """保存本插件托管的站点 ID 映射。"""
        self.save_data(self._MANAGED_SITES_DATA_KEY, managed)

    @staticmethod
    def _normalize_timeout(value: Any) -> int:
        """规范化超时秒数。"""
        try:
            timeout = int(value)
        except (TypeError, ValueError):
            timeout = 30
        return max(5, min(timeout, 120))
