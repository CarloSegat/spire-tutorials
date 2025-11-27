#!/bin/sh

# key pairs
openssl genrsa -out broker_webapp.key 2048
openssl genrsa -out broker_server.key 2048

openssl genrsa -out stock_quote.key 2048
openssl genrsa -out stock_server.key 2048

## servers self-signed cert
openssl req -new -x509 -key broker_server.key -out agent-cacert.broker.pem -days 3650 -subj "/CN=broker CA"
openssl req -new -x509 -key stock_server.key -out agent-cacert.stock.pem -days 3650 -subj "/CN=stock market CA"

## webapp CSR
openssl req -new -key broker_webapp.key -out broker_webapp.csr -subj "/CN=webapp agent" -config agent.csr.cnf -extensions v3_ext
openssl x509 -req -in broker_webapp.csr -CA agent-cacert.broker.pem -CAkey broker_server.key -CAcreateserial -out agent.broker.crt.pem -days 365 -sha256 -extfile agent.csr.cnf -extensions v3_ext

## stock service csr
openssl req -new -key stock_quote.key -out stock_quote.csr -subj "/CN=quotes-service agent" -config agent.csr.cnf -extensions v3_ext
openssl x509 -req -in stock_quote.csr -CA agent-cacert.stock.pem -CAkey stock_server.key -CAcreateserial -out agent.stock.crt.pem -days 365 -sha256 -extfile agent.csr.cnf -extensions v3_ext

## move certificates 

mv agent-cacert.broker.pem ../docker/spire-server-broker.example/conf/agent-cacert.pem
mv agent-cacert.stock.pem ../docker/spire-server-stockmarket.example/conf/agent-cacert.pem

mv agent.broker.crt.pem ../docker/example-workload/conf/agent.crt.pem
mv broker_webapp.key ../docker/example-workload/conf/agent.key.pem

mv agent.stock.crt.pem ../docker/stock-quotes-service/conf/agent.crt.pem
mv stock_quote.key ../docker/stock-quotes-service/conf/agent.key.pem