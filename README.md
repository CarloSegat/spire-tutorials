# SPIRE Tutorials Fork

## Useful commands

Bundles
`docker compose -f ./docker-compose.yaml exec -T spire-server-broker bin/spire-server bundle show` 

`docker compose -f ./docker-compose.yaml exec -T spire-server-broker /opt/spire/bin/spire-server bundle show -format spiffe >`

sh into container without container id
`docker compose -f ./docker-compose.yaml exec -T broker-webapp /bin/sh`

healthcheck of spiffe agents/servers
`docker compose -f ./docker-compose.yaml exec -T broker-webapp bin/spire-agent healthcheck`



## TEMP
Before running 2-bootstrap-federation the bundle has 1 entry:

`docker compose -f ./docker-compose.yaml exec -T spire-server-broker \
    /opt/spire/bin/spire-server bundle show -format spiffe
{
    "keys": [
        {
            "use": "x509-svid",
            "kty": "EC",
            "crv": "P-256",
            "x": "oOTDdo5HNOrdH46KMH0Owy2wVmrsZAckgL_6ZU8IgOQ",
            "y": "tFzBfCX918KTwinsinNrHp5sXTabmLCmYkqJm7an5iA",
            "x5c": [
                "MIICAzCCAaigAwIBAgIQSPTFaJQl/0KR14OPNX2X8zAKBggqhkjOPQQDAjBPMQswCQYDVQQGEwJVUzEPMA0GA1UEChMGU1BJRkZFMS8wLQYDVQQFEyY5Njk3NTM0MDA1MDI2Njk3ODc5MzMzMjI0MTc2MzI3MzY0NDAxOTAeFw0yNTEwMDYxNDAyMzRaFw0yNTEwMDcxNDAyNDRaME8xCzAJBgNVBAYTAlVTMQ8wDQYDVQQKEwZTUElGRkUxLzAtBgNVBAUTJjk2OTc1MzQwMDUwMjY2OTc4NzkzMzMyMjQxNzYzMjczNjQ0MDE5MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEoOTDdo5HNOrdH46KMH0Owy2wVmrsZAckgL/6ZU8IgOS0XMF8Jf3XwpPCKeyKc2senmxdNpuYsKZiSombtqfmIKNmMGQwDgYDVR0PAQH/BAQDAgEGMA8GA1UdEwEB/wQFMAMBAf8wHQYDVR0OBBYEFM/u0SgWRBdcnXSRvgzwEFykZ3JXMCIGA1UdEQQbMBmGF3NwaWZmZTovL2Jyb2tlci5leGFtcGxlMAoGCCqGSM49BAMCA0kAMEYCIQC3y6fA/MaoIXPGmsy2I0VXz3ywbj4jaRHgpg7wSH4pdgIhAO1x92zdSkAuz4QMltaokdMuvg//Rc09kxuggiHY/mtx"
            ]
        },
        {
            "use": "jwt-svid",
            "kty": "EC",
            "kid": "ev8HrZfHytpzvbP0kYH3yIUfvSPu2f8t",
            "crv": "P-256",
            "x": "r5ybt-a1f4lnkn2335lfyli3JQMosJtlrK4Zyp0pAT4",
            "y": "z2pAGCqak6A878l1WzdHJ2zbxHTsxa4bDS-YkQLnWJ8"
        }
    ],
    "spiffe_sequence": 1
}`

after it has 2, likely this is the effect of the set bundle command: 

`docker compose -f ./docker-compose.yaml exec -T spire-server-broker \      
    /opt/spire/bin/spire-server bundle show -format spiffe
{
    "keys": [
        {
            "use": "x509-svid",
            "kty": "EC",
            "crv": "P-256",
            "x": "gkj2G3bUx4PnT3QwsCZmZ3p12YPqldYAnsAMb4ETRSA",
            "y": "cNKNVY-jzNbOYLfmLphidKR8aQHCJc0p4G3yysdjXvU",
            "x5c": [
                "MIICAzCCAaigAwIBAgIQNlXbIgZeRhFNxv5tGBhSUzAKBggqhkjOPQQDAjBPMQswCQYDVQQGEwJVUzEPMA0GA1UEChMGU1BJRkZFMS8wLQYDVQQFEyY3MjIyNDEwMTU0ODc5MjUyMjY1Njg2NTczODI4NTQ2NDk2NTcxNTAeFw0yNTEwMDIxMzI1MDhaFw0yNTEwMDMxMzI1MThaME8xCzAJBgNVBAYTAlVTMQ8wDQYDVQQKEwZTUElGRkUxLzAtBgNVBAUTJjcyMjI0MTAxNTQ4NzkyNTIyNjU2ODY1NzM4Mjg1NDY0OTY1NzE1MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEgkj2G3bUx4PnT3QwsCZmZ3p12YPqldYAnsAMb4ETRSBw0o1Vj6PM1s5gt+YumGJ0pHxpAcIlzSngbfLKx2Ne9aNmMGQwDgYDVR0PAQH/BAQDAgEGMA8GA1UdEwEB/wQFMAMBAf8wHQYDVR0OBBYEFE/Pljnyyp0aJ5+euXBD3LQMn9hEMCIGA1UdEQQbMBmGF3NwaWZmZTovL2Jyb2tlci5leGFtcGxlMAoGCCqGSM49BAMCA0kAMEYCIQCfLFAiRJXcH6L5CZBgINeTVhoDHc3ycpfxBrKUC687vAIhAPtHiHBZIjvkIHIPQduJLaNZ8x2Pyp9SFMzLcobjZF2i"
            ]
        },
        {
            "use": "x509-svid",
            "kty": "EC",
            "crv": "P-256",
            "x": "uClirvZSmxQGAKc4zjq52KtXrMfQVF4ETiaWKC923Fw",
            "y": "Kv6uxSc75GK4ks6su_yNBanDaOwYujcPSNCBb2wxZkk",
            "x5c": [
                "MIICBTCCAaqgAwIBAgIQX/iFkUfB8/3oTLDnAYIrVTAKBggqhkjOPQQDAjBQMQswCQYDVQQGEwJVUzEPMA0GA1UEChMGU1BJRkZFMTAwLgYDVQQFEycxMjc1NjcwNTgyOTEyNTI0MDYwMTc1NTQyMjk1NjgyOTI5MjQyNDUwHhcNMjUxMDA2MTM1ODA2WhcNMjUxMDA3MTM1ODE2WjBQMQswCQYDVQQGEwJVUzEPMA0GA1UEChMGU1BJRkZFMTAwLgYDVQQFEycxMjc1NjcwNTgyOTEyNTI0MDYwMTc1NTQyMjk1NjgyOTI5MjQyNDUwWTATBgcqhkjOPQIBBggqhkjOPQMBBwNCAAS4KWKu9lKbFAYApzjOOrnYq1esx9BUXgROJpYoL3bcXCr+rsUnO+RiuJLOrLv8jQWpw2jsGLo3D0jQgW9sMWZJo2YwZDAOBgNVHQ8BAf8EBAMCAQYwDwYDVR0TAQH/BAUwAwEB/zAdBgNVHQ4EFgQU518461evInIUcVtUiEMSAVpdSiwwIgYDVR0RBBswGYYXc3BpZmZlOi8vYnJva2VyLmV4YW1wbGUwCgYIKoZIzj0EAwIDSQAwRgIhAKSt641SyJ4z+KUdN+Oi0RwWzREh9Qko1iJTmr6qJrbsAiEAjYUEECndqNnh90eb8BALdtpuIz5W9vWTTljylOYG6ds="
            ]
        },
        {
            "use": "jwt-svid",
            "kty": "EC",
            "kid": "QbYSx5bG6A1b6JsdB2cSXZE6BgGJHXg1",
            "crv": "P-256",
            "x": "FsNetrnzYSHw59PEqHnjSgbrG6Tw0zbB5m90MDA4ED8",
            "y": "ZASQy7YohewzjDJUh54hAjhe5ADKCys4v5vkn8Cah68"
        },
        {
            "use": "jwt-svid",
            "kty": "EC",
            "kid": "QZURFRZQ01Fb1EqsGFSM87N1I42Tqlhv",
            "crv": "P-256",
            "x": "ePzAPDdCLJkjZGv33j462BDC5t3hNx6334_rD19avZk",
            "y": "E5F8TnsO1bRVTyK4h-oxvz2LHvwSQY_Qk1gu84Dyqeo"
        }
    ],
    "spiffe_sequence": 3
}`