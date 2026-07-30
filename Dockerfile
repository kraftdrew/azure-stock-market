FROM public.ecr.aws/lambda/python:3.12

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt --target "${LAMBDA_TASK_ROOT}"

COPY src/stock_market_pipeline "${LAMBDA_TASK_ROOT}/stock_market_pipeline"

CMD ["stock_market_pipeline.extract.lambda_handler"]
