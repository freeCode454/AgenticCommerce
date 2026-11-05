# 后端 Python 3.12 生产镜像构建文件
FROM python:3.12-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖定义并安装
COPY pyproject.toml .
RUN pip install --no-cache-dir pip -U && \
    pip install --no-cache-dir .

# 复制业务代码与提示词
COPY app/ ./app/
COPY prompts/ ./prompts/
COPY main.py .
COPY run_workflow.py .

EXPOSE 8002

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
