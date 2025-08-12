# Use AWS Lambda Python runtime
FROM public.ecr.aws/lambda/python:3.12

# Copy requirements and install dependencies
COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py ${LAMBDA_TASK_ROOT}/
COPY listeners/ ${LAMBDA_TASK_ROOT}/listeners/
COPY utils/ ${LAMBDA_TASK_ROOT}/utils/

# Set the CMD to your handler (app.lambda_handler)
CMD ["app.lambda_handler"]