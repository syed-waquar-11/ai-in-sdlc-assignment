using InvoiceApp.Domain;
using Xunit;

namespace InvoiceApp.Tests;

public class ArchitectureTests
{
    [Fact]
    public void DomainAssembly_DoesNotDirectlyReferenceApiOrAspNetCore()
    {
        var references = typeof(ApprovalService).Assembly.GetReferencedAssemblies();

        Assert.DoesNotContain(references, reference =>
            reference.Name == "InvoiceApp.Api" ||
            (reference.Name?.StartsWith("Microsoft.AspNetCore.", StringComparison.Ordinal) ?? false));
    }
}
