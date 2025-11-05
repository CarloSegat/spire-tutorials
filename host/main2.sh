#!/bin/sh

./0_post_bundle.sh 2 stockmarket.example
./0_post_bundle.sh 1 broker.example


./1_set_bundle.sh 2 broker.example
./1_set_bundle.sh 1 stockmarket.example


./2_create_federation_dynamic.sh 2 broker.example 8082
./2_create_federation_dynamic.sh 1 stockmarket.example 8084


# ./3_registration_entries.sh 1 1 broker.example stockmarket.example 
# ./3_registration_entries.sh 2 1 stockmarket.example broker.example 

