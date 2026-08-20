# ADR 0002: Run on Amazon ECS with Fargate behind an ALB, not AWS App Runner

| | |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-20 |
| Author | Kimberly D. Kight |
| Decision reference | D-2 |

## Context

The prototype ships as a single container image containing the FastAPI backend
and the built frontend assets, and needs a public URL reviewers can test.
[Source: Deliverables; Decision D-3]

Two constraints narrow the field. The workload is CPU bound: local OCR runs
inside the container on every request (Decision D-4), and the 5-second response
target is the binding requirement. [Source: Sarah Chen interview] And the
intended production environment is AWS GovCloud (US), where a service that does
not exist is not an option. [Source: Decision D-11]

Federal deployment adds a gate that commercial deployment does not: a service
that is not on the AWS FedRAMP services-in-scope list creates an authorization
problem regardless of its technical merits. Marcus Williams describes what that
process costs: "Took 18 months just for the paperwork."
[Source: Marcus Williams interview]

## Decision

Run the container on **Amazon ECS with the AWS Fargate launch type**, behind an
**Application Load Balancer**, with the image stored in **Amazon ECR**.

## Alternatives considered

### AWS App Runner

Would be the simplest option: point it at an image, get a URL and TLS, with no
load balancer, task definition, or service to configure.

**Excluded because App Runner is not on the AWS FedRAMP services-in-scope
list.** [Source: Decision D-2] For a system whose intended production
environment is federal, building the prototype on a service that cannot follow
it into production would mean discarding the deployment work later. This is a
compliance constraint, not a technical judgment about the service.

The current contents of the AWS list must be confirmed at deployment time
against https://aws.amazon.com/compliance/services-in-scope/FedRAMP/ rather than
taken from this document. This ADR records the decision and its stated basis; it
does not itself assert the list's current contents.

### Amazon EKS

Kubernetes would offer the most control and the most portable workload
definition.

Not chosen because it is disproportionate to a single-container prototype. EKS
adds a control plane to pay for and a cluster to operate, patch, and secure, for
one stateless service. Marcus's framing applies: "for a prototype? Just don't do
anything crazy." [Source: Marcus Williams interview]

### Amazon EC2 with Docker

Would be conceptually simple and cheap at this scale.

Not chosen because it makes the team responsible for host patching, hardening,
and lifecycle management. In a federal context those become documented control
obligations. Fargate removes the host from the authorization boundary.

### AWS Lambda with a container image

Attractive for a spiky, per-request workload, and cheap when idle.

Not chosen for two reasons rooted in this workload. Cold starts are a direct
threat to the 5-second target, and this project has explicit evidence that
latency determines adoption: "If we can't get results back in about 5 seconds,
nobody's going to use it." [Source: Sarah Chen interview] Second, batch
submissions of 200 to 300 labels sit awkwardly inside Lambda's per-invocation
limits, and would push the design toward an asynchronous job model that the
prototype's scope does not include. [Source: Sarah Chen interview]

No latency comparison between these options was measured. This reasoning is
about known execution models, not about benchmark results.

## Consequences

**Positive**

- No servers to patch. Fargate removes host management from the boundary.
- The ALB provides TLS termination and a health check target, which the
  container already exposes at `GET /api/health`.
- ECS, ECR, ELB, IAM, and CloudWatch are long-established AWS services, which
  supports the GovCloud portability goal (NFR-10).
- Task CPU and memory are configurable, which matters for a CPU-bound OCR
  workload under a latency target.

**Negative**

- More infrastructure to define than App Runner: cluster, task definition,
  service, target group, load balancer, security groups, and IAM roles. All of
  it must be written before anything deploys.
- An ALB has an hourly cost that runs whether or not the prototype is being
  used.
- Slower first deployment than a platform-as-a-service option.

**Risks accepted**

- That task sizing is wrong on the first attempt. OCR is CPU bound and no
  latency measurement exists yet, so sizing cannot be chosen responsibly until
  the performance tier runs. Tracked in
  [../09_DEPLOYMENT.md](../09_DEPLOYMENT.md) section 7.
- That the FedRAMP status of any service used here changes. Mitigated by
  confirming status at deployment time rather than relying on this record.

## References

- [../05_ARCHITECTURE.md](../05_ARCHITECTURE.md) section 2
- [../09_DEPLOYMENT.md](../09_DEPLOYMENT.md)
- [../06_SECURITY_AND_COMPLIANCE.md](../06_SECURITY_AND_COMPLIANCE.md) section 4
