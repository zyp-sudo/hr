"""Database migration helpers — add auth columns to users table if missing.

Run on startup::

    from app.db.migrations import ensure_auth_schema
    ensure_auth_schema()

Idempotent — safe to call on every startup.
"""

from __future__ import annotations

import logging

from sqlalchemy import text

from app.db.session import engine

logger = logging.getLogger(__name__)

_AUTH_COLUMNS = [
    ("password_hash", "VARCHAR(255) NOT NULL DEFAULT ''", "bcrypt 密码哈希"),
    ("is_active", "BOOLEAN NOT NULL DEFAULT TRUE", "账户是否激活"),
    ("role", "VARCHAR(20) NOT NULL DEFAULT 'user'", "角色: admin / user"),
    ("session_id", "VARCHAR(64) NULL DEFAULT NULL", "当前活跃会话ID"),
]


_USERS_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '用户ID',
    name VARCHAR(120) NOT NULL COMMENT '用户姓名',
    email VARCHAR(255) NULL UNIQUE COMMENT '邮箱',
    phone VARCHAR(50) NULL COMMENT '手机号',
    city VARCHAR(100) NULL COMMENT '所在城市',
    education_summary JSON NULL COMMENT '教育背景摘要',
    project_summary JSON NULL COMMENT '项目经历摘要',
    target_position VARCHAR(255) NULL COMMENT '求职意向岗位',
    target_city VARCHAR(100) NULL COMMENT '求职意向城市',
    expected_salary_min INT NULL COMMENT '期望最低薪资',
    expected_salary_max INT NULL COMMENT '期望最高薪资',
    password_hash VARCHAR(255) NOT NULL DEFAULT '' COMMENT 'bcrypt 密码哈希',
    is_active BOOLEAN NOT NULL DEFAULT TRUE COMMENT '账户是否激活',
    role VARCHAR(20) NOT NULL DEFAULT 'user' COMMENT '角色: admin / user',
    session_id VARCHAR(64) NULL DEFAULT NULL COMMENT '当前活跃会话ID',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_users_email (email),
    INDEX idx_users_phone (phone),
    INDEX idx_users_city (city),
    INDEX idx_users_target_position (target_position),
    INDEX idx_users_target_city (target_city),
    INDEX idx_users_updated_at (updated_at),
    INDEX idx_users_city_target (city, target_position)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';
"""


def ensure_auth_schema() -> None:
    """Create ``users`` table if missing; add auth columns if table exists."""
    with engine.connect() as conn:
        # 1 — Ensure the table itself exists
        row = conn.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name = 'users'"
            )
        ).scalar()
        if not row:
            logger.info("Creating users table …")
            conn.execute(text(_USERS_TABLE_DDL))
            conn.commit()
            logger.info("users table created successfully")
            return

        # 2 — Table exists: add any missing auth columns (legacy migration)
        existing = {
            r[0]
            for r in conn.execute(
                text(
                    "SELECT COLUMN_NAME FROM information_schema.columns "
                    "WHERE table_schema = DATABASE() AND table_name = 'users'"
                )
            ).fetchall()
        }

        added = 0
        for col_name, col_def, col_comment in _AUTH_COLUMNS:
            if col_name in existing:
                continue
            try:
                conn.execute(
                    text(
                        f"ALTER TABLE users ADD COLUMN {col_name} {col_def} "
                        f"COMMENT '{col_comment}'"
                    )
                )
                conn.commit()
                logger.info("Added column users.%s", col_name)
                added += 1
            except Exception:
                logger.exception("Failed to add column users.%s", col_name)

        if added:
            logger.info("Auth migration complete: %d columns added", added)
        else:
            logger.info("Auth columns already present — nothing to migrate")


# ======================================================================
# AI Hub tables
# ======================================================================

_AI_PROVIDERS_DDL = """
CREATE TABLE IF NOT EXISTS ai_providers (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '供应商ID',
    name VARCHAR(255) NOT NULL COMMENT '显示名称',
    provider_type VARCHAR(50) NOT NULL COMMENT '供应商类型',
    base_url VARCHAR(512) NULL COMMENT 'API 基础地址',
    api_key_encrypted TEXT NULL COMMENT 'Fernet 加密后的 API Key',
    extra_config JSON NULL COMMENT '额外配置',
    is_active BOOLEAN NOT NULL DEFAULT TRUE COMMENT '是否启用',
    description TEXT NULL COMMENT '备注说明',
    sort_order INT NOT NULL DEFAULT 0 COMMENT '排序权重',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE INDEX idx_ai_providers_name (name),
    INDEX idx_ai_providers_type (provider_type),
    INDEX idx_ai_providers_updated_at (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='AI 供应商表';
"""

_AI_MODELS_DDL = """
CREATE TABLE IF NOT EXISTS ai_models (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '模型ID',
    provider_id BIGINT NOT NULL COMMENT '所属供应商',
    model_id VARCHAR(255) NOT NULL COMMENT 'API 模型标识符',
    display_name VARCHAR(255) NULL COMMENT '前端展示名称',
    model_type VARCHAR(50) NOT NULL DEFAULT 'llm' COMMENT '模型类型',
    max_input_tokens INT NULL COMMENT '最大输入 token 数',
    max_output_tokens INT NULL COMMENT '最大输出 token 数',
    supports_vision BOOLEAN NOT NULL DEFAULT FALSE COMMENT '是否支持图片识别',
    supports_tools BOOLEAN NOT NULL DEFAULT FALSE COMMENT '是否支持 function calling',
    supports_streaming BOOLEAN NOT NULL DEFAULT TRUE COMMENT '是否支持流式输出',
    pricing_input_per_1k FLOAT NULL COMMENT '输入价格',
    pricing_output_per_1k FLOAT NULL COMMENT '输出价格',
    extra_params JSON NULL COMMENT '默认参数',
    is_active BOOLEAN NOT NULL DEFAULT TRUE COMMENT '是否启用',
    sort_order INT NOT NULL DEFAULT 0 COMMENT '排序权重',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_ai_models_provider (provider_id),
    INDEX idx_ai_models_type (model_type),
    INDEX idx_ai_models_updated_at (updated_at),
    CONSTRAINT fk_ai_models_provider FOREIGN KEY (provider_id) REFERENCES ai_providers(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='AI 模型表';
"""


def ensure_ai_hub_schema() -> None:
    """Create ``ai_providers`` and ``ai_models`` tables if they don't exist."""
    with engine.connect() as conn:
        # providers
        conn.execute(text(_AI_PROVIDERS_DDL))
        # models
        conn.execute(text(_AI_MODELS_DDL))
        conn.commit()
    logger.info("AI Hub schema migration complete")


# ======================================================================
# Demo homepage jobs — 10 static showcase records
# ======================================================================

_DEMO_JOBS_DDL = """
CREATE TABLE IF NOT EXISTS demo_homepage_jobs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID',
    title VARCHAR(255) NOT NULL COMMENT '岗位名称',
    company VARCHAR(255) NOT NULL COMMENT '公司名称',
    city VARCHAR(100) NOT NULL DEFAULT '不限' COMMENT '工作城市',
    salary VARCHAR(100) NOT NULL DEFAULT '面议' COMMENT '薪资范围',
    skills VARCHAR(500) NOT NULL DEFAULT '' COMMENT '技能标签，逗号分隔',
    summary VARCHAR(500) NOT NULL DEFAULT '' COMMENT '岗位简介，1-2句话',
    industry VARCHAR(100) NOT NULL DEFAULT '互联网' COMMENT '所属行业',
    sort_order INT NOT NULL DEFAULT 0 COMMENT '排序权重',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='主页展示用10条Demo岗位数据';
"""

_DEMO_JOBS_SEED = [
    ("高级后端工程师", "阿里巴巴", "杭州", "35K-55K", "Java,Go,微服务,分布式架构,MySQL,Redis,K8s", "负责核心交易链路高并发架构设计与稳定性建设，参与双11大促保障。", "互联网/电商", 1),
    ("AI 算法工程师", "腾讯", "深圳", "40K-60K", "Python,PyTorch,LLM,RAG,NLP,Transformer", "负责大语言模型在智能客服场景的落地，包括微调、推理优化与效果评估。", "互联网/AI", 2),
    ("资深前端工程师", "字节跳动", "北京", "30K-50K", "React,TypeScript,Node.js,Webpack,Vite,可视化", "负责抖音电商中后台前端架构设计、组件库搭建与性能优化。", "互联网/电商", 3),
    ("高级产品经理", "美团", "北京", "28K-45K", "产品规划,数据分析,SQL,用户研究,AB测试", "负责外卖配送效率优化产品，通过数据和用户洞察驱动产品迭代。", "互联网/O2O", 4),
    ("数据工程师", "华为", "深圳", "30K-50K", "Spark,Flink,Hadoop,Hive,数据仓库,ETL", "负责数据中台实时计算管道建设，支撑业务数据大屏与决策分析。", "通信/IT", 5),
    ("DevOps 工程师", "网易", "广州", "28K-42K", "Docker,Kubernetes,CI/CD,Terraform,Prometheus,Grafana", "负责游戏业务线基础设施自动化运维，推进容器化与混合云架构治理。", "互联网/游戏", 6),
    ("安全工程师", "蚂蚁集团", "杭州", "35K-55K", "渗透测试,安全审计,SDL,WAF,IDS/IPS,加密协议", "负责支付系统安全架构评审、漏洞挖掘与安全合规体系建设。", "金融科技", 7),
    ("测试开发工程师", "拼多多", "上海", "25K-40K", "自动化测试,性能测试,Jenkins,Selenium,Appium,Python", "负责电商核心链路的测试框架搭建与质量保障体系建设。", "互联网/电商", 8),
    ("数据分析师", "京东", "北京", "22K-38K", "SQL,Python,Tableau,AB实验,用户画像,机器学习", "负责物流业务线数据看板搭建、经营分析与增长策略数据支撑。", "互联网/电商", 9),
    ("技术总监", "小米", "北京", "50K-80K", "技术管理,架构设计,团队建设,战略规划,跨部门协作", "负责IoT平台技术战略制定，管理50+人技术团队，推动AIoT生态建设。", "智能硬件/IoT", 10),
]


def ensure_demo_jobs_schema() -> None:
    """Create ``demo_homepage_jobs`` table and seed 10 records if empty."""
    with engine.connect() as conn:
        conn.execute(text(_DEMO_JOBS_DDL))
        conn.commit()

        count = conn.execute(
            text("SELECT COUNT(*) FROM demo_homepage_jobs")
        ).scalar()
        if count == 0:
            for title, company, city, salary, skills, summary, industry, sort_order in _DEMO_JOBS_SEED:
                conn.execute(
                    text(
                        "INSERT INTO demo_homepage_jobs "
                        "(title, company, city, salary, skills, summary, industry, sort_order) "
                        "VALUES (:t, :c, :ci, :s, :sk, :su, :ind, :so)"
                    ),
                    {"t": title, "c": company, "ci": city, "s": salary, "sk": skills,
                     "su": summary, "ind": industry, "so": sort_order},
                )
            conn.commit()
            logger.info("Seeded 10 demo homepage jobs")
        else:
            logger.info("Demo homepage jobs already present (%d rows)", count)
