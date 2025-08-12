# Simple Dockerfile - just use pip with requirements
FROM public.ecr.aws/lambda/python:3.12

# Copy source files
COPY pyproject.toml ./
COPY agent/ ${LAMBDA_TASK_ROOT}/agent/
COPY main.py ${LAMBDA_TASK_ROOT}/

# Install dependencies directly with pip (simpler than uv for Lambda)
RUN pip install --no-cache-dir -e . --target ${LAMBDA_TASK_ROOT}

# Set AWS Lambda handler
CMD ["main.lambda_handler"]